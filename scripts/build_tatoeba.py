#!/usr/bin/env python3
"""Build a slim English↔Chinese sentence-pair database from Tatoeba dumps.

Output: backend/data/tatoeba.db with schema
    CREATE TABLE pairs (en TEXT NOT NULL, zh TEXT NOT NULL, en_len INTEGER NOT NULL);
    CREATE VIRTUAL TABLE pairs_fts USING fts5(en, content='pairs', content_rowid='rowid');

Run from the repo root:

    python3 scripts/build_tatoeba.py

Optional flags:
    --keep-raw     don't delete the raw .tsv files after building
    --raw-dir DIR  where to download/look for raw files (default: ./.tatoeba-raw)

The raw files are ~150MB compressed and we only need eng+cmn rows, so we stream
them line by line — peak memory stays modest.
"""

from __future__ import annotations

import argparse
import bz2
import os
import shutil
import sqlite3
import sys
import urllib.request
from pathlib import Path

# Tatoeba weekly dumps live here. Files are not authenticated and free to use
# under CC-BY-2.0 (https://tatoeba.org/en/terms_of_use).
SENTENCES_URL = "https://downloads.tatoeba.org/exports/sentences.tar.bz2"
LINKS_URL = "https://downloads.tatoeba.org/exports/links.tar.bz2"

# Mandarin Chinese is "cmn" in Tatoeba; some entries also use "yue" (Cantonese)
# and historical "zho". We include cmn only by default — yue translations are
# rarely useful to mainland learners.
EN_LANG = "eng"
ZH_LANGS = {"cmn"}

DEFAULT_RAW_DIR = Path(".tatoeba-raw")
DEFAULT_OUT = Path("backend/data/tatoeba.db")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    sentences_tsv = args.raw_dir / "sentences.tsv"
    links_tsv = args.raw_dir / "links.tsv"

    download_and_extract(SENTENCES_URL, sentences_tsv)
    download_and_extract(LINKS_URL, links_tsv)

    print(f"→ Reading sentences from {sentences_tsv} (filtering to {EN_LANG} + {ZH_LANGS})")
    en_by_id, zh_by_id = load_sentences(sentences_tsv)
    print(f"   en: {len(en_by_id):,}    zh: {len(zh_by_id):,}")

    print(f"→ Reading links from {links_tsv}")
    pairs = load_pairs(links_tsv, en_by_id, zh_by_id)
    print(f"   pair count: {len(pairs):,}")

    print(f"→ Writing {args.out}")
    write_db(args.out, pairs)

    if not args.keep_raw:
        shutil.rmtree(args.raw_dir, ignore_errors=True)
        print(f"   raw files removed (use --keep-raw to keep)")
    print("✓ done")
    return 0


def download_and_extract(url: str, target_tsv: Path) -> None:
    """Download a .tar.bz2 from Tatoeba and extract the single .tsv inside.

    Tatoeba's archives contain one file each (sentences.csv, links.csv) — the
    "csv" is actually tab-separated. We extract straight to `target_tsv`.
    """
    if target_tsv.exists() and target_tsv.stat().st_size > 0:
        print(f"✓ {target_tsv} already exists, skipping download")
        return
    print(f"→ Downloading {url}")
    tmp_archive = target_tsv.with_suffix(".tar.bz2")
    urllib.request.urlretrieve(url, tmp_archive)
    # tarfile is overkill; bz2 + raw read works because each archive holds one
    # member, but to be safe we use the tarfile module.
    import tarfile
    with tarfile.open(tmp_archive, "r:bz2") as tar:
        members = [m for m in tar.getmembers() if m.isfile()]
        if not members:
            raise RuntimeError(f"empty archive: {url}")
        # Extract first regular file as the target tsv
        m = members[0]
        with tar.extractfile(m) as src, open(target_tsv, "wb") as dst:
            shutil.copyfileobj(src, dst)
    tmp_archive.unlink(missing_ok=True)


def load_sentences(path: Path) -> tuple[dict[int, str], dict[int, str]]:
    """Stream the sentences TSV and return id → text dicts for eng and cmn."""
    en: dict[int, str] = {}
    zh: dict[int, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                sid = int(parts[0])
            except ValueError:
                continue
            lang = parts[1]
            text = parts[2].strip()
            if not text:
                continue
            if lang == EN_LANG:
                en[sid] = text
            elif lang in ZH_LANGS:
                zh[sid] = text
    return en, zh


def load_pairs(
    path: Path,
    en_by_id: dict[int, str],
    zh_by_id: dict[int, str],
) -> list[tuple[str, str]]:
    """Walk the link list; whenever (en_id, zh_id) or (zh_id, en_id), emit a pair."""
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[int, int]] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            a, _, b = line.rstrip("\n").partition("\t")
            try:
                aid = int(a)
                bid = int(b)
            except ValueError:
                continue
            if aid in en_by_id and bid in zh_by_id:
                pair_key = (aid, bid)
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                pairs.append((en_by_id[aid], zh_by_id[bid]))
    return pairs


def write_db(out: Path, pairs: list[tuple[str, str]]) -> None:
    if out.exists():
        out.unlink()
    conn = sqlite3.connect(out)
    conn.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE pairs (en TEXT NOT NULL, zh TEXT NOT NULL, en_len INTEGER NOT NULL);
        """
    )
    conn.executemany(
        "INSERT INTO pairs (en, zh, en_len) VALUES (?, ?, ?)",
        ((en, zh, len(en)) for en, zh in pairs),
    )
    conn.executescript(
        """
        CREATE VIRTUAL TABLE pairs_fts USING fts5(en, content='pairs', content_rowid='rowid');
        INSERT INTO pairs_fts(rowid, en) SELECT rowid, en FROM pairs;
        CREATE INDEX idx_pairs_len ON pairs(en_len);
        """
    )
    conn.commit()
    conn.close()
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"   wrote {len(pairs):,} pairs, {size_mb:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
