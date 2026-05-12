"""Offline dictionary + example sentence lookup.

Two read-only SQLite databases sit next to the user data DB under backend/data/:
- ecdict.db   — ECDICT (skywind3000/ECDICT) for word data (IPA, pos, translation).
- tatoeba.db  — Pre-built English↔Chinese sentence pairs, schema below.

Both are optional. If a file is missing or has unexpected shape, the relevant
lookup returns empty/None instead of raising. This means the app still works on
a fresh install before install.sh has finished downloading the dictionaries.

tatoeba.db schema (built by scripts/build_tatoeba.py):
    CREATE TABLE pairs (en TEXT NOT NULL, zh TEXT NOT NULL, en_len INTEGER);
    CREATE VIRTUAL TABLE pairs_fts USING fts5(en, content='pairs', content_rowid='rowid');
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

# Tatoeba's "cmn" lang code mixes Simplified and Traditional Chinese sentences.
# We always serve Simplified to match the rest of the UI. zhconv is pure-Python
# (~700KB) with no native deps; if for some reason it's not installed (older
# environments before requirements.txt was updated), we fall through to the
# raw text rather than crash.
try:
    import zhconv  # type: ignore

    def _to_simplified(text: str) -> str:
        return zhconv.convert(text, "zh-cn") if text else text
except ImportError:
    def _to_simplified(text: str) -> str:
        return text

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ECDICT_PATH = _DATA_DIR / "ecdict.db"
TATOEBA_PATH = _DATA_DIR / "tatoeba.db"

# Connection caches — sqlite3 connections aren't shareable across threads by
# default, so we keep one per (thread, db).
_local = threading.local()


def _conn(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    key = f"conn_{path.name}"
    conn = getattr(_local, key, None)
    if conn is None:
        # uri=True + mode=ro makes it explicit we never write
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        setattr(_local, key, conn)
    return conn


def has_ecdict() -> bool:
    return ECDICT_PATH.exists()


def has_tatoeba() -> bool:
    return TATOEBA_PATH.exists()


# ─── ECDICT ─────────────────────────────────────────────────────────────────

# Pull the head form out of "0:lemma" inside ECDICT's "exchange" field, e.g.
# "p:ran/d:run/i:running/3:runs/s:runs" → for "ran", exchange has "0:run".
_EXCHANGE_LEMMA_RE = re.compile(r"(?:^|/)0:([^/]+)")


def _ecdict_row(conn: sqlite3.Connection, word: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT word, phonetic, definition, translation, pos, exchange "
        "FROM stardict WHERE word = ? COLLATE NOCASE LIMIT 1",
        (word,),
    ).fetchone()
    return row


def lookup_ecdict(word: str) -> dict[str, Any] | None:
    """Look up an English word in ECDICT. Returns:
        { "text", "phonetic", "pos", "translation" }
    or None if the word (and its inflections) cannot be found.
    """
    conn = _conn(ECDICT_PATH)
    if conn is None:
        return None

    w = word.strip().lower()
    if not w:
        return None

    try:
        row = _ecdict_row(conn, w)
        # If not found, try resolving via inflection table — look up the word
        # in any row's exchange field to find the lemma, then look up the lemma.
        if row is None:
            lemma = _resolve_lemma(conn, w)
            if lemma and lemma != w:
                row = _ecdict_row(conn, lemma)
        if row is None:
            return None
    except sqlite3.DatabaseError:
        return None

    phonetic = (row["phonetic"] or "").strip()
    if phonetic and not phonetic.startswith("/"):
        phonetic = f"/{phonetic}/"

    pos_raw = (row["pos"] or "").strip()
    pos = _format_pos(pos_raw)

    translation = (row["translation"] or "").strip()
    # ECDICT separates senses with \n — normalise to ；for consistency with AI output.
    translation = re.sub(r"\s*\n\s*", "；", translation)

    return {
        "text": (row["word"] or w).strip().lower(),
        "phonetic": phonetic,
        "pos": pos,
        "translation": translation,
    }


def _resolve_lemma(conn: sqlite3.Connection, inflected: str) -> str | None:
    """Find the base form of an inflected word by scanning ECDICT's exchange field.

    The exchange field of the LEMMA row lists its inflections (e.g. for "run":
    "p:ran/d:run/i:running/3:runs/s:runs"). So we look for any row whose
    exchange contains a code mapping to our inflected form.
    """
    like = f"%:{inflected}%"
    row = conn.execute(
        "SELECT word FROM stardict WHERE exchange LIKE ? LIMIT 1",
        (like,),
    ).fetchone()
    return row["word"] if row else None


_POS_LABELS = {
    "n": "n.",
    "v": "v.",
    "a": "adj.",
    "adj": "adj.",
    "r": "adv.",
    "adv": "adv.",
    "prep": "prep.",
    "conj": "conj.",
    "pron": "pron.",
    "interj": "interj.",
    "phr": "phr.",
}


def _format_pos(raw: str) -> str:
    """ECDICT pos field looks like "n:5/v:2/a:1". Take the codes, sorted by
    count desc, and turn into "n./v./adj." style."""
    if not raw:
        return ""
    parts: list[tuple[str, int]] = []
    for chunk in raw.split("/"):
        if ":" not in chunk:
            continue
        code, _, count = chunk.partition(":")
        try:
            n = int(count)
        except ValueError:
            n = 0
        label = _POS_LABELS.get(code.strip().lower())
        if label:
            parts.append((label, n))
    if not parts:
        return ""
    parts.sort(key=lambda x: -x[1])
    seen: list[str] = []
    for label, _ in parts:
        if label not in seen:
            seen.append(label)
    return "/".join(seen)


# ─── Tatoeba ────────────────────────────────────────────────────────────────


def search_tatoeba(word: str, limit: int = 5) -> list[dict[str, str]]:
    """Return up to `limit` example sentence pairs containing the word.

    Strategy:
    - FTS5 match on the lowercased word (whole-word match by FTS tokenizer).
    - Bias toward variety: pick sentences of different lengths (short → long)
      so the UI's easy-to-hard ordering still feels right.
    - Each example: {"en": "...", "zh": "..."}.
    """
    conn = _conn(TATOEBA_PATH)
    if conn is None:
        return []

    w = word.strip().lower()
    if not w:
        return []

    try:
        # Pull a larger pool than we need, then bucket by length.
        rows = conn.execute(
            "SELECT p.en, p.zh, p.en_len FROM pairs_fts f "
            "JOIN pairs p ON p.rowid = f.rowid "
            "WHERE pairs_fts MATCH ? "
            "ORDER BY p.en_len ASC LIMIT 60",
            (_fts_query(w),),
        ).fetchall()
    except sqlite3.DatabaseError:
        return []

    if not rows:
        return []

    # Bucket by length quartile to get variety, then pick `limit` total.
    rows = [r for r in rows if r["en"] and r["zh"]]
    if not rows:
        return []
    rows.sort(key=lambda r: r["en_len"])
    picked = _pick_variety(rows, limit)
    return [{"en": r["en"], "zh": _to_simplified(r["zh"])} for r in picked]


_FTS_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _fts_query(word: str) -> str:
    """Build a safe FTS5 query. We only allow ASCII letters / apostrophe /
    hyphen — anything else gets stripped to avoid breaking the parser."""
    tokens = _FTS_TOKEN_RE.findall(word)
    if not tokens:
        return f'"{word}"'  # fall back to phrase — sqlite will quote-escape itself
    # FTS5 phrase: "exact phrase" — works even if user typed a multi-word lookup
    safe = " ".join(tokens)
    return f'"{safe}"'


def _pick_variety(rows: list[sqlite3.Row], limit: int) -> list[sqlite3.Row]:
    """Pick `limit` rows spread across the length distribution."""
    if len(rows) <= limit:
        return rows
    step = len(rows) / limit
    return [rows[int(i * step)] for i in range(limit)]
