# 单词星标 ⭐ 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single boolean `Word.starred` field with a cross-cutting "⭐ 重点" tile in Library and quick-toggle UI in three places (Library word rows, WordDetail header, Reader's bottom word panel). Solves "我不知道要练习哪些单词" by giving users one-click curation of a focus set.

**Architecture:** Add column via existing idempotent `ensure_schema` pattern. New endpoint `POST /api/words/{id}/star` accepts the target state (not a toggle) for idempotency. Frontend uses optimistic UI everywhere — local mutation first, rollback + toast on failure. `allWords` ref in Library is the single source of truth; all three view modes derive from it via existing computed, so star changes propagate automatically.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite, Vue 3 Composition API + TypeScript, existing `api` client.

---

## File Structure

**Backend (modify):**
- `backend/app/models.py` — add `starred` and (for completeness in client) `wrong_count` is already there but not exposed; we only add `starred`
- `backend/app/db.py` — one line in `ensure_schema()`
- `backend/app/schemas.py` — add `starred` to `WordOut` and `WordBrief`; add `wrong_count` to `WordBrief`; add `StarUpdate`
- `backend/app/routes/words.py` — add `POST /{word_id}/star`; extend `preview_word` to return `id` + `starred` when already saved

**Frontend (modify):**
- `frontend/src/api.ts` — add `starred` + `wrong_count` to types; add `setStarred` method; extend `WordPreview` `found+already_saved` variant with `id` + `starred`
- `frontend/src/views/Library.vue` — `buckets` computed adds "⭐ 重点" entry; word rows get star button; sort function for starred bucket; `onStarredChanged` handler
- `frontend/src/components/WordDetail.vue` — star button in header, emits `starred-changed`
- `frontend/src/views/Reader.vue` — track id+starred in `selected` ref; render star button when id present

**No new files.**

---

## Task 1: Backend — Add `starred` column and expose `wrong_count`

**Files:**
- Modify: `backend/app/models.py:31-51` (Word model)
- Modify: `backend/app/db.py:30-50` (ensure_schema)
- Modify: `backend/app/schemas.py:20-48` (WordOut + WordBrief)

- [ ] **Step 1: Add `starred` column to `Word` model**

Edit `backend/app/models.py`. Inside `class Word`, add right after `next_review_at`:

```python
    starred = Column(Boolean, nullable=False, default=False, server_default="0", index=True)
```

Also add `Boolean` to the SQLAlchemy import line:

```python
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
```

- [ ] **Step 2: Add migration in `ensure_schema`**

Edit `backend/app/db.py`. Inside the `with engine.begin() as conn:` block of `ensure_schema()`, add to the `if "words" in tables:` group:

```python
            _add_column_if_missing(conn, "words", "starred",
                                   "starred BOOLEAN NOT NULL DEFAULT 0")
```

- [ ] **Step 3: Expose `starred` and `wrong_count` in schemas**

Edit `backend/app/schemas.py`.

Change `WordOut` to include `starred`:

```python
class WordOut(BaseModel):
    id: int
    text: str
    phonetic: str
    pos: str
    translation: str
    category: str
    mastery: int
    review_count: int
    correct_count: int
    starred: bool
    created_at: datetime
    next_review_at: datetime
    examples: List[ExampleOut]

    class Config:
        from_attributes = True
```

Change `WordBrief` to include `starred` and `wrong_count` (computed from review_count - correct_count via a pydantic computed field, since `Word` doesn't store wrong_count directly):

```python
class WordBrief(BaseModel):
    id: int
    text: str
    phonetic: str
    translation: str
    category: str
    mastery: int
    starred: bool
    wrong_count: int
    created_at: datetime

    class Config:
        from_attributes = True
```

Then we need `wrong_count` to materialize. Since `from_attributes = True` looks up by attribute, and `Word` doesn't have `wrong_count`, add a `@property` on the model. Edit `backend/app/models.py` inside `class Word`, after the columns:

```python
    @property
    def wrong_count(self) -> int:
        return max(0, (self.review_count or 0) - (self.correct_count or 0))
```

- [ ] **Step 4: Add `StarUpdate` schema**

Edit `backend/app/schemas.py`. Add after `WordCreate`:

```python
class StarUpdate(BaseModel):
    starred: bool
```

- [ ] **Step 5: Restart backend and verify schema migration ran**

```bash
cd /Users/mm/wordglass/backend && .venv/bin/python -c "
from app.db import ensure_schema, engine
from sqlalchemy import inspect
ensure_schema()
cols = [c['name'] for c in inspect(engine).get_columns('words')]
print('starred' in cols, sorted(cols))
"
```

Expected: prints `True` followed by the column list including `starred`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/app/schemas.py
git commit -m "Backend: add Word.starred column + expose wrong_count

starred is a per-word boolean managed by the user via the upcoming
POST /api/words/{id}/star endpoint and Library/Reader/WordDetail star
buttons. wrong_count is now exposed on WordBrief so the frontend can
sort the '⭐ 重点' bucket by error rate. Migration is idempotent via
ensure_schema's ALTER TABLE ADD COLUMN helper."
```

---

## Task 2: Backend — Add `POST /{word_id}/star` and extend `preview`

**Files:**
- Modify: `backend/app/routes/words.py:23` (imports) and append new route

- [ ] **Step 1: Import `StarUpdate`**

Edit `backend/app/routes/words.py`. Change the schemas import:

```python
from ..schemas import StarUpdate, WordBrief, WordCreate, WordOut
```

- [ ] **Step 2: Extend `preview_word` to return id + starred when already saved**

Edit the `preview_word` function (around line 53). Change the body to:

```python
@router.get("/preview")
def preview_word(
    text: str = Query(..., min_length=1, max_length=80),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Instant ECDICT lookup for the reader-panel tooltip. Never writes."""
    hit = lookup_ecdict(text.strip().lower())
    if hit is None:
        return {"found": False, "text": text}
    existing = db.query(Word).filter(
        Word.text == hit["text"], Word.user_id == user.id
    ).first()
    return {
        "found": True,
        "text": hit["text"],
        "phonetic": hit["phonetic"],
        "pos": hit["pos"],
        "translation": hit["translation"],
        "already_saved": existing is not None,
        "id": existing.id if existing else None,
        "starred": existing.starred if existing else False,
    }
```

- [ ] **Step 3: Add `POST /{word_id}/star` endpoint**

Append to `backend/app/routes/words.py` at the end of the file:

```python
@router.post("/{word_id}/star", response_model=WordOut)
def set_starred(
    word_id: int,
    body: StarUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    w = db.get(Word, word_id)
    if not w or w.user_id != user.id:
        raise HTTPException(status_code=404, detail="word not found")
    w.starred = body.starred
    db.commit()
    db.refresh(w)
    return w
```

- [ ] **Step 4: Restart backend and smoke-test with curl**

```bash
cd /Users/mm/wordglass/backend && .venv/bin/uvicorn app.main:app --port 8000 &
sleep 2
# Get any existing word id from sqlite (replace with a real id if known)
WID=$(.venv/bin/python -c "
from app.db import SessionLocal
from app.models import Word
db = SessionLocal()
w = db.query(Word).first()
print(w.id if w else 0)
")
echo "Testing on word_id=$WID"
# Without auth this will 401; with TOKEN env it works. Just verify the route exists:
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/api/words/$WID/star \
  -H 'Content-Type: application/json' -d '{"starred":true}'
kill %1 2>/dev/null
```

Expected: `401` (auth required) — proves the route is wired up. (`404` if WID=0 from empty db is also fine.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/words.py
git commit -m "Backend: POST /api/words/{id}/star + return id+starred from preview

The endpoint accepts the desired state in the body (not a toggle) so the
client can retry safely. preview_word now returns the saved word's id and
starred state when already_saved=true so the Reader's word panel can
render a star button for words already in the library."
```

---

## Task 3: Frontend — API client types and method

**Files:**
- Modify: `frontend/src/api.ts:24-48` (types), `:250-271` (api object)

- [ ] **Step 1: Add `starred` + `wrong_count` to types**

Edit `frontend/src/api.ts`. Change `WordOut`:

```typescript
export interface WordOut {
  id: number;
  text: string;
  phonetic: string;
  pos: string;
  translation: string;
  category: string;
  mastery: number;
  review_count: number;
  correct_count: number;
  starred: boolean;
  created_at: string;
  next_review_at: string;
  examples: Example[];
}
```

Change `WordBrief`:

```typescript
export interface WordBrief {
  id: number;
  text: string;
  phonetic: string;
  translation: string;
  category: string;
  mastery: number;
  starred: boolean;
  wrong_count: number;
  created_at: string;
}
```

Change `WordPreview` to include the new fields in the `found` variant:

```typescript
export type WordPreview =
  | { found: true; text: string; phonetic: string; pos: string;
      translation: string; already_saved: boolean;
      id: number | null; starred: boolean }
  | { found: false; text: string };
```

- [ ] **Step 2: Add `setStarred` method**

Edit `frontend/src/api.ts`. Inside the `api` object, after `deleteWord`, add:

```typescript
  setStarred: (id: number, starred: boolean) =>
    request<WordOut>(`/api/words/${id}/star`, {
      method: "POST",
      body: JSON.stringify({ starred }),
    }),
```

- [ ] **Step 3: Verify build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -8
```

Expected: `✓ built in <X>ms` with no errors. Type errors here would surface from WordBrief/WordOut consumers that we haven't updated yet — those should auto-pass since adding required fields to types is breaking only if old code constructs the type, and our code only reads it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api.ts
git commit -m "API client: starred + wrong_count types and setStarred method"
```

---

## Task 4: Library — "⭐ 重点" tile + star toggle on word rows

**Files:**
- Modify: `frontend/src/views/Library.vue` (most of script and template)

- [ ] **Step 1: Extend `CategoryBucket` interface and add `sortStarred`**

In the `<script setup>` of Library.vue, change the bucket interface and add a sort helper. Replace the `interface CategoryBucket` block:

```typescript
interface CategoryBucket {
  name: string;
  total: number;
  words: WordBrief[];
  avgMastery: number;
  isUncategorized: boolean;
  isStarred: boolean;
}
```

Update `toBucket` to default `isStarred: false`:

```typescript
function toBucket(name: string, words: WordBrief[], isUncat: boolean): CategoryBucket {
  const sorted = [...words].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
  const avg =
    words.reduce((s, w) => s + (w.mastery || 0), 0) / Math.max(1, words.length);
  return {
    name,
    total: words.length,
    words: sorted,
    avgMastery: avg,
    isUncategorized: isUncat,
    isStarred: false,
  };
}
```

Add after `toBucket`:

```typescript
function sortStarred(words: WordBrief[]): WordBrief[] {
  return [...words].sort((a, b) => {
    if (b.wrong_count !== a.wrong_count) return b.wrong_count - a.wrong_count;
    if (a.mastery !== b.mastery) return a.mastery - b.mastery;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}
```

- [ ] **Step 2: Update `buckets` computed to prepend "⭐ 重点"**

Replace the `buckets` computed:

```typescript
const buckets = computed<CategoryBucket[]>(() => {
  const byCat: Record<string, WordBrief[]> = {};
  for (const w of allWords.value) {
    const cat = w.category || "未分类";
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(w);
  }
  const result: CategoryBucket[] = [];

  // ⭐ 重点 first if any
  const starred = allWords.value.filter((w) => w.starred);
  if (starred.length > 0) {
    const sorted = sortStarred(starred);
    const avg =
      starred.reduce((s, w) => s + (w.mastery || 0), 0) / starred.length;
    result.push({
      name: "⭐ 重点",
      total: starred.length,
      words: sorted,
      avgMastery: avg,
      isUncategorized: false,
      isStarred: true,
    });
  }

  // Uncategorized next
  if ((byCat["未分类"] || []).length > 0) {
    result.push(toBucket("未分类", byCat["未分类"], true));
  }
  // Other categories
  for (const name of cats.value.order) {
    if (name === "未分类") continue;
    const words = byCat[name] || [];
    if (words.length === 0) continue;
    result.push(toBucket(name, words, false));
  }
  // Fallback for unknown-order categories
  for (const [name, words] of Object.entries(byCat)) {
    if (name === "未分类") continue;
    if (cats.value.order.includes(name)) continue;
    if (words.length === 0) continue;
    result.push(toBucket(name, words, false));
  }
  return result;
});
```

- [ ] **Step 3: Add `toggleStar` and `onStarredChanged` functions**

Add to the script setup (near `onDeleted`):

```typescript
async function toggleStar(w: WordBrief, event?: MouseEvent) {
  event?.stopPropagation();
  const target = !w.starred;
  w.starred = target;
  try {
    await api.setStarred(w.id, target);
  } catch (e: any) {
    w.starred = !target;
    message.value = e.message || "操作失败";
    setTimeout(() => { message.value = ""; }, 4000);
  }
}

function onStarredChanged(id: number, starred: boolean) {
  const w = allWords.value.find((x) => x.id === id);
  if (w) w.starred = starred;
}
```

- [ ] **Step 4: Render star button in word rows (category + search views)**

In the template, find the `<div class="word-row">` blocks. There are two — one inside `cat-view`, one inside `search-view`. Update both so that just before the closing `</div>` of `word-row`, the star button appears (between `row-text` and `row-pips`).

For both word-row blocks, replace:

```vue
            <div class="row-pips">
              <span
                v-for="(on, i) in masteryPips(w.mastery)"
                :key="i"
                class="p"
                :class="{ on }"
              />
            </div>
```

with:

```vue
            <button
              class="row-star"
              :class="{ on: w.starred }"
              :title="w.starred ? '取消重点' : '设为重点'"
              @click="toggleStar(w, $event)"
            >{{ w.starred ? '★' : '☆' }}</button>
            <div class="row-pips">
              <span
                v-for="(on, i) in masteryPips(w.mastery)"
                :key="i"
                class="p"
                :class="{ on }"
              />
            </div>
```

- [ ] **Step 5: Style the "⭐ 重点" tile and `.row-star`**

In the `<style scoped>` of Library.vue, add after `.tile.uncat::before`:

```css
.tile.starred {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
}
.tile.starred::before {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--accent) 10%, transparent),
    transparent 60%
  );
}
.tile.starred .tile-name { color: var(--accent); }
```

And before the `.row-pips` block, add:

```css
.row-star {
  appearance: none;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 4px 6px;
  color: var(--text-tertiary);
  transition: color 150ms ease, transform 100ms ease;
  flex-shrink: 0;
}
.row-star:hover { color: var(--accent); }
.row-star.on { color: var(--accent); }
.row-star:active { transform: scale(0.85); }
```

- [ ] **Step 6: Apply `.starred` class to the tile**

In the template's tile button (the `v-for` over `buckets`), change the existing class binding:

```vue
        <button
          v-for="b in buckets"
          :key="b.name"
          class="tile glass"
          :class="{ uncat: b.isUncategorized, starred: b.isStarred }"
          @click="enterCategory(b.name)"
        >
```

- [ ] **Step 7: Hook up `WordDetail` event**

In the template, change the `WordDetail` line to listen for `starred-changed`:

```vue
    <WordDetail
      :word-id="detailId"
      @close="closeDetail"
      @deleted="onDeleted"
      @starred-changed="onStarredChanged"
    />
```

- [ ] **Step 8: Build to verify**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -8
```

Expected: clean build.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/Library.vue
git commit -m "Library: ⭐ 重点 tile + star toggle in word rows

Adds a cross-cutting '⭐ 重点' tile at the top of the tile grid that
aggregates all starred words, sorted by wrong_count DESC, mastery ASC,
created_at DESC. Each word row in the category and search views gets a
☆/★ button that toggles via api.setStarred with optimistic UI."
```

---

## Task 5: WordDetail — star button in header

**Files:**
- Modify: `frontend/src/components/WordDetail.vue`

- [ ] **Step 1: Add emit + toggleStar in script setup**

Edit `frontend/src/components/WordDetail.vue`. Change the `defineEmits` call:

```typescript
const emit = defineEmits<{
  (e: "close"): void;
  (e: "deleted", wordId: number): void;
  (e: "starred-changed", wordId: number, starred: boolean): void;
}>();
```

Add after `handleDelete`:

```typescript
async function toggleStar() {
  if (!word.value) return;
  const target = !word.value.starred;
  word.value.starred = target;
  try {
    await api.setStarred(word.value.id, target);
    emit("starred-changed", word.value.id, target);
  } catch (e: any) {
    word.value.starred = !target;
    error.value = e.message || "操作失败";
    setTimeout(() => { error.value = ""; }, 4000);
  }
}
```

- [ ] **Step 2: Render star button in the header**

In the template inside the `<div class="head">` block, locate the `<div class="word-row">` with the word text and speaker button. Right after the closing `</div>` of `word-row`, but before the `<div class="meta">`, add:

```vue
                <div class="head-actions">
                  <button
                    class="star-btn"
                    :class="{ on: word.starred }"
                    @click="toggleStar"
                  >{{ word.starred ? '★ 已重点' : '☆ 标重点' }}</button>
                </div>
```

- [ ] **Step 3: Style the star button**

Add to the `<style scoped>` block of WordDetail.vue (near the other header styles):

```css
.head-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
.star-btn {
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-dim);
  padding: 6px 14px;
  border-radius: 999px;
  font: inherit;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
}
.star-btn:hover {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
  color: var(--text-primary);
}
.star-btn.on {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--glass-border));
  color: var(--accent);
  font-weight: 600;
}
```

- [ ] **Step 4: Build and commit**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -8
cd /Users/mm/wordglass && git add frontend/src/components/WordDetail.vue
git commit -m "WordDetail: ⭐ 标重点 toggle in drawer header

Emits 'starred-changed' so Library can sync the local allWords entry
without a refetch."
```

---

## Task 6: Reader — star button in bottom word panel

**Files:**
- Modify: `frontend/src/views/Reader.vue`

- [ ] **Step 1: Locate the `selected` ref shape**

Find the `const selected = ref(...)` declaration in Reader.vue. It tracks loaded preview state (text, phonetic, pos, translation, alreadySaved, loading, found, adding, addError). We need to add `id: number | null` and `starred: boolean`.

Search for `alreadySaved` to find the type/object. Update the inline type to include the two new fields wherever it's defined/assigned (typically at preview load and in `addSelectedWord`).

- [ ] **Step 2: Wire id + starred from preview response**

Locate where `selected.value` is set after `api.previewWord(...)`. Change the assignment to include `id` and `starred` (both come from the extended backend response we made in Task 2):

```typescript
selected.value = {
  text: hit.text,
  phonetic: hit.found ? hit.phonetic : "",
  pos: hit.found ? hit.pos : "",
  translation: hit.found ? hit.translation : "",
  alreadySaved: hit.found ? hit.already_saved : false,
  id: hit.found ? hit.id : null,
  starred: hit.found ? hit.starred : false,
  found: hit.found,
  loading: false,
  adding: false,
  addError: "",
};
```

(Adjust to match the existing object shape exactly — keep all keys that were there, just add the two new ones. Use `hit.found && 'id' in hit ? hit.id : null` if TS narrowing demands.)

- [ ] **Step 3: Wire id + starred after `addSelectedWord` succeeds**

In `addSelectedWord`, after the `const created = await api.addWord(...)` call (or equivalent), update the `selected.value` fields:

```typescript
        selected.value.id = created.id;
        selected.value.starred = created.starred;
        selected.value.alreadySaved = true;
```

(Look for where `alreadySaved = true` is currently set after a successful add and add the two new lines alongside it.)

- [ ] **Step 4: Add `togglePanelStar` function**

Add near `addSelectedWord`:

```typescript
async function togglePanelStar() {
  if (!selected.value || selected.value.id == null) return;
  const target = !selected.value.starred;
  selected.value.starred = target;
  try {
    await api.setStarred(selected.value.id, target);
  } catch (e: any) {
    if (selected.value) selected.value.starred = !target;
  }
}
```

- [ ] **Step 5: Render star button in the panel**

In the `word-panel` template block (the `wp-actions` div around line 515), add the star button between the saved badge / add button and the close button. Replace:

```vue
          <div class="wp-actions">
            <span v-if="selected.alreadySaved" class="wp-saved">✓ 已在单词库</span>
            <button
              v-else
              class="btn btn-primary wp-add-btn"
              :disabled="selected.adding"
              @click="addSelectedWord"
            >
              {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
            </button>
            <button class="btn btn-ghost wp-close-btn" @click="closeSelected">关闭</button>
          </div>
```

with:

```vue
          <div class="wp-actions">
            <span v-if="selected.alreadySaved" class="wp-saved">✓ 已在单词库</span>
            <button
              v-else
              class="btn btn-primary wp-add-btn"
              :disabled="selected.adding"
              @click="addSelectedWord"
            >
              {{ selected.adding ? "添加中…" : "+ 加入单词库" }}
            </button>
            <button
              v-if="selected.id != null"
              class="wp-star"
              :class="{ on: selected.starred }"
              @click="togglePanelStar"
            >{{ selected.starred ? '★ 重点' : '☆ 标重点' }}</button>
            <button class="btn btn-ghost wp-close-btn" @click="closeSelected">关闭</button>
          </div>
```

- [ ] **Step 6: Style `.wp-star`**

Add to the `<style scoped>` of Reader.vue, near the other `.wp-*` styles:

```css
.wp-star {
  appearance: none;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-dim);
  padding: 6px 12px;
  border-radius: 999px;
  font: inherit;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 150ms ease, color 150ms ease, border-color 150ms ease;
}
.wp-star:hover {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
  color: var(--text-primary);
}
.wp-star.on {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--glass-border));
  color: var(--accent);
  font-weight: 600;
}
```

- [ ] **Step 7: Build and commit**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -8
cd /Users/mm/wordglass && git add frontend/src/views/Reader.vue
git commit -m "Reader: ⭐ star toggle in bottom word panel

The panel only shows the star button for words already in the user's
library (need an id to PATCH). When the user just added a word, the id
and starred state are wired in from the addWord response."
```

---

## Task 7: Build + manual smoke

**Files:** (none — this task is verification)

- [ ] **Step 1: Full frontend build**

```bash
cd /Users/mm/wordglass/frontend && npm run build 2>&1 | tail -10
```

Expected: clean build, no TS errors.

- [ ] **Step 2: Restart backend + open app**

```bash
cd /Users/mm/wordglass/backend && .venv/bin/uvicorn app.main:app --port 8000 &
sleep 2
open http://localhost:8000/ 2>/dev/null || true
```

- [ ] **Step 3: Smoke checklist**

In the browser, log in and verify:

- Library: no "⭐ 重点" tile yet (no starred words)
- Click any word row in a category — drawer opens with "☆ 标重点" button in header
- Click the button — turns to "★ 已重点", drawer's title stays the same
- Close drawer — Library tile grid shows new "⭐ 重点" tile at the top (orange-ish border)
- Click the "⭐ 重点" tile body — drills into the category view, the word is listed with ★ on the right
- Click ★ next to the word — turns to ☆, tile disappears (or count decreases)
- Re-star a word, click "▶ 练这 1 个" on the tile — Practice page loads with `?word_ids=…` and just that word
- Open Reader, paste a paragraph with a word already in your library, click the word — bottom panel shows "☆ 标重点" button (because id known), click it — Library now shows that word starred
- Open Reader, click an unfamiliar word — panel shows "+ 加入单词库" but NO star button (no id yet); click "+ 加入单词库" — after the add, star button appears
- Search box in Library: type the starred word's text → search view shows ★ next to it; click ★ to unstar
- Delete a starred word from WordDetail — the "⭐ 重点" tile updates immediately

- [ ] **Step 4: Build mobile sanity**

Resize browser to <900px:
- "⭐ 重点" tile takes full width
- Word rows in category view stack single column
- Star buttons are tappable (not cropped)

- [ ] **Step 5: Push**

```bash
cd /Users/mm/wordglass && git push origin main
```

---

## Self-Review (controller checklist before handing off)

**Spec coverage:**
- ✅ Section 2 (data model): Task 1 adds `starred` column + index + wrong_count property
- ✅ Section 3 (API): Task 2 adds POST /star + extends preview
- ✅ Section 4 (frontend api client): Task 3
- ✅ Section 5 (Library): Task 4 — tile + star button + sort
- ✅ Section 6 (WordDetail): Task 5
- ✅ Section 7 (Reader): Task 6
- ✅ Section 9 (initial starred=false): handled by SQLAlchemy `default=False` in models.py + server_default
- ✅ Section 10 (errors): Tasks 4/5/6 all rollback + toast
- ✅ Section 11 (acceptance): Task 7 smoke covers each item

**Placeholders:** None — all code blocks are complete.

**Type consistency:**
- `setStarred(id, starred): WordOut` — used identically in Library `toggleStar`, WordDetail `toggleStar`, Reader `togglePanelStar`
- `starred-changed` event emits `(id, starred)` — listened to as `onStarredChanged(id, starred)`
- `WordBrief.starred: boolean` + `WordBrief.wrong_count: number` — consistent in backend `WordBrief` pydantic model and frontend type

**Risks flagged:**
- Reader's `selected` ref is referenced from multiple places; Step 6.2 says "adjust to match the existing object shape exactly" — implementer should read the current shape before editing, not blindly replace
- WordDetail's `head-actions` div is new; CSS targets `.head-actions` which must be inside `.head` for layout
