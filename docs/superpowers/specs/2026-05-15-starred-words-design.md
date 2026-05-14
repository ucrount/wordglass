# 单词星标 · ⭐ 重点

**日期**: 2026-05-15
**目标**: 让用户能跨分类、单字粒度地标记"我想重点练习的词"。Library 顶部多一张「⭐ 重点」磁贴聚合所有星标词，"▶ 练这 N 个" 直跳专练。解决"词越来越多，不知道练哪些"的问题。

---

## 1. 范围与约束

### 范围内
- 后端：`Word.starred` 字段 + `POST /api/words/{id}/star` + 现有 `WordOut`/`WordBrief` 多一个 `starred` 字段
- 前端：
  - `Library.vue`：多一张「⭐ 重点」磁贴 + 词行右侧 ⭐ 切换
  - `WordDetail.vue`：抽屉顶部 ⭐ 切换
  - `Reader.vue`：底部单词面板 ⭐ 切换
- DB 迁移：通过 `db.py::ensure_schema` 幂等 `ALTER TABLE ADD COLUMN`

### 范围外
- 不做用户自定义命名标签（一词一布尔即可）
- 不做"批量打星"功能（每次单字操作）
- 不动 Practice 视图的核心交互
- 不动 Dashboard（暂不显示"重点词"专门组件）
- 不动后端推荐 / SRS 算法

### 不能损坏
- 现有的 Library 三视图（tiles / category / search）
- WordDetail 抽屉的删除、音标、例句、TTS
- Reader 的翻译流程、底部单词面板的"加入词库"按钮
- 用户隔离（每个用户只能看到/操作自己的星标）

---

## 2. 数据模型

### 2.1 `Word.starred`

```python
# backend/app/models.py
class Word(Base):
    # … existing columns …
    starred = Column(Boolean, nullable=False, default=False, server_default="0")
```

### 2.2 迁移

```python
# backend/app/db.py - inside ensure_schema()
_add_column_if_missing(conn, "words", "starred", "BOOLEAN NOT NULL DEFAULT 0")
```

复用现有 `_add_column_if_missing` helper（如不存在则按现状 user_id 迁移那段的同样模式）。SQLite 不允许添加带默认非空且非常量的列，但 `BOOLEAN ... DEFAULT 0` 是常量，安全。

---

## 3. API

### 3.1 Schema 更新

```python
# backend/app/schemas.py
class WordBrief(BaseModel):
    id: int
    text: str
    phonetic: str
    translation: str
    category: str
    mastery: int
    starred: bool          # 新增
    created_at: datetime

class WordOut(BaseModel):
    # … existing fields …
    starred: bool          # 新增
```

### 3.2 切换端点

```
POST /api/words/{id}/star
Body: { "starred": true }   # 目标状态，不是 toggle
Response: WordOut           # 完整更新后的词
```

**为什么不用 toggle**：避免乐观更新和服务器状态不一致。前端送目标值，幂等。

实现：

```python
# backend/app/routes/words.py
class StarUpdate(BaseModel):
    starred: bool

@router.post("/{word_id}/star", response_model=WordOut)
def set_starred(
    word_id: int,
    body: StarUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    w = db.query(Word).filter(Word.id == word_id, Word.user_id == user.id).first()
    if not w:
        raise HTTPException(404, "word not found")
    w.starred = body.starred
    db.commit()
    db.refresh(w)
    return w
```

### 3.3 list 端点扩展（可选筛选）

```python
@router.get("", response_model=list[WordBrief])
def list_words(
    q: str | None = None,
    category: str | None = None,
    mastery: int | None = None,
    starred: bool | None = None,    # 新增
    limit: int = 50,
    ...
):
    query = base_query_for_user(user)
    if starred is not None:
        query = query.filter(Word.starred == starred)
    ...
```

（Library 客户端已经一次性拿 500 个词，靠 computed 切片，但留这个接口给未来分页用。）

---

## 4. 前端：API client

```typescript
// frontend/src/api.ts
export interface WordBrief {
  id: number;
  text: string;
  phonetic: string;
  translation: string;
  category: string;
  mastery: number;
  starred: boolean;       // 新增
  created_at: string;
}

export interface WordOut {
  // … existing …
  starred: boolean;       // 新增
}

// In api object:
async setStarred(id: number, starred: boolean): Promise<WordOut> {
  return req<WordOut>(`/api/words/${id}/star`, {
    method: "POST",
    body: JSON.stringify({ starred }),
  });
},
```

---

## 5. Library 改造

### 5.1 「⭐ 重点」磁贴

#### 5.1.1 buckets computed 增量

```typescript
// In Library.vue, inside buckets computed
const starredWords = allWords.value.filter(w => w.starred);
if (starredWords.length > 0) {
  result.unshift({  // 插到最前
    name: "⭐ 重点",
    total: starredWords.length,
    words: sortStarred(starredWords),
    avgMastery: avg(starredWords),
    isUncategorized: false,
    isStarred: true,           // 新标志位
  });
}
```

CategoryBucket 接口多一个可选 `isStarred?: boolean`。

#### 5.1.2 「重点」磁贴的特殊样式

- 边框：`color-mix(in srgb, var(--accent) 30%, var(--glass-border))`（和未分类同色调，但内部样式区分）
- 背景渐变：用 `var(--brand)` 的微光（不用 accent，区分于未分类）
- 名字前缀：⭐ 已经在 `name` 里，不另加 dot
- CTA：「▶ 练这 N 个」

#### 5.1.3 排序

「重点」内部按 `wrong_count DESC, mastery ASC` 排（错的多 + 不熟的最前）。

**等等**：`WordBrief` 没有 `wrong_count` 字段。两个选项：
- (A) 给 `WordBrief` 加 `wrong_count` 字段（后端早就有这列，schema 加一行）
- (B) 按 `mastery ASC, created_at DESC` 排（不熟的最前，同 mastery 按新加的优先）

选 **(A)**：信号更强，"我错过的"比"我不熟的"更明确指向"重点"。

```python
# schemas.py
class WordBrief(BaseModel):
    # …
    wrong_count: int       # 新增（已在 DB，只是没暴露）
```

```typescript
// api.ts
export interface WordBrief {
  // …
  wrong_count: number;
}
```

排序：

```typescript
function sortStarred(words: WordBrief[]): WordBrief[] {
  return [...words].sort((a, b) => {
    if (b.wrong_count !== a.wrong_count) return b.wrong_count - a.wrong_count;
    if (a.mastery !== b.mastery) return a.mastery - b.mastery;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}
```

#### 5.1.4 磁贴位置

排序结果：
1. ⭐ 重点（若有）
2. 未分类（若有）
3. 其它分类（按 cats.order）

### 5.2 词行的 ⭐ 切换

#### 5.2.1 模板

```vue
<!-- 在 word-row 内，row-pips 之前 -->
<button
  class="row-star"
  :class="{ on: w.starred }"
  :title="w.starred ? '取消重点' : '设为重点'"
  @click.stop="toggleStar(w)"
>
  {{ w.starred ? '★' : '☆' }}
</button>
```

#### 5.2.2 处理

```typescript
async function toggleStar(w: WordBrief) {
  const target = !w.starred;
  // 乐观更新
  w.starred = target;
  try {
    await api.setStarred(w.id, target);
  } catch (e: any) {
    w.starred = !target;  // 回滚
    message.value = e.message || "操作失败";
    setTimeout(() => (message.value = ""), 4000);
  }
}
```

注意：因为 `allWords` 里的对象就是 `categoryWords` / `searchResults` 引用的同一份（computed 不复制），直接改 `w.starred` 会触发所有视图重新计算 buckets，"重点"磁贴会即时跟进。

#### 5.2.3 样式

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
}
.row-star:hover { color: var(--accent); }
.row-star.on { color: var(--accent); }
.row-star:active { transform: scale(0.85); }
```

### 5.3 磁贴样例词不显示星

磁贴上的样例词是预览，不显示星标（保持紧凑）。星标只在词行（drill-down 后）和单词详情里显示。

---

## 6. WordDetail 抽屉

抽屉顶部 header 区，加一个 ⭐ 按钮。

### 6.1 模板（嵌入现有 detail header）

```vue
<div class="detail-head">
  <h2 class="detail-word">{{ word.text }}</h2>
  <div class="detail-actions">
    <button
      class="star-btn"
      :class="{ on: word.starred }"
      @click="toggleStar"
    >{{ word.starred ? '★ 已重点' : '☆ 标重点' }}</button>
    <!-- 现有的删除按钮 -->
    <button class="delete-btn" @click="handleDelete">删除</button>
  </div>
</div>
```

### 6.2 处理

```typescript
async function toggleStar() {
  if (!word.value) return;
  const target = !word.value.starred;
  word.value.starred = target;          // 乐观
  try {
    await api.setStarred(word.value.id, target);
    emit("starred-changed", word.value.id, target);  // 通知父组件刷新
  } catch (e: any) {
    word.value.starred = !target;       // 回滚
    error.value = e.message || "操作失败";
  }
}
```

### 6.3 父组件 (Library) 处理

```typescript
function onStarredChanged(id: number, starred: boolean) {
  const w = allWords.value.find(x => x.id === id);
  if (w) w.starred = starred;
}
```

Library 模板：

```vue
<WordDetail
  :word-id="detailId"
  @close="closeDetail"
  @deleted="onDeleted"
  @starred-changed="onStarredChanged"
/>
```

### 6.4 样式

```css
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
  transition: all 150ms ease;
}
.star-btn:hover {
  border-color: color-mix(in srgb, var(--accent) 30%, var(--glass-border));
}
.star-btn.on {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  border-color: color-mix(in srgb, var(--accent) 40%, var(--glass-border));
  color: var(--accent);
  font-weight: 600;
}
```

---

## 7. Reader 底部单词面板

Reader 底部的"已选中单词"面板（点击译文词后弹出的那个），加 ⭐ 切换按钮。

### 7.1 数据来源

Reader 现有的 word panel 里展示的是 `selectedWord` ref（一个完整的 `WordOut`）。后端在 `/api/words/preview` 或加词后返回的 word 已包含 `starred`。

### 7.2 模板

```vue
<!-- Reader.vue 的 word-panel 内部，在"加入词库"按钮旁 -->
<button
  v-if="selectedWord && selectedWord.id"   <!-- 只有已加入词库的词才能星标 -->
  class="panel-star"
  :class="{ on: selectedWord.starred }"
  @click="togglePanelStar"
>{{ selectedWord.starred ? '★ 重点' : '☆ 标重点' }}</button>
```

未加入词库的预览词不显示星按钮（没 id 怎么标）。

### 7.3 处理

```typescript
async function togglePanelStar() {
  if (!selectedWord.value || !selectedWord.value.id) return;
  const target = !selectedWord.value.starred;
  selectedWord.value.starred = target;
  try {
    await api.setStarred(selectedWord.value.id, target);
  } catch (e: any) {
    selectedWord.value.starred = !target;
    panelMessage.value = e.message || "操作失败";
  }
}
```

### 7.4 样式

复用 WordDetail 的 `.star-btn` 思路，命名 `.panel-star`，按 Reader 现有 panel 风格略调。

---

## 8. Practice 视图

**不动**。Practice 已经支持 `?word_ids=` focus 模式，Library 的「重点」磁贴 CTA 直接跳就行。

是否在 Practice 卡片角落显示 ⭐ 提示？暂不做（避免心智干扰；用户已经知道是星标在练）。

---

## 9. 加词时的初始状态

新加的词：`starred = false`。无需用户选择。

---

## 10. 错误处理

- `setStarred` 网络失败 → UI 回滚 + toast 提示
- 词不存在（404）→ 回滚 + toast「词已不存在」
- 用户跨设备同步：每次 Library 进入会 `loadAll()`，星标会刷新到最新

---

## 11. 验收

- 后端
  - `ALTER TABLE` 幂等，重启不报错
  - `POST /api/words/{id}/star` 切换状态，返回完整 word
  - `WordOut` / `WordBrief` 都返回 `starred` 字段
  - 跨用户隔离：用户 A 不能操作用户 B 的词（已通过 `current_user` filter 保证）
- 前端
  - Library 词行右侧有 ⭐ / ★，点击切换，立刻反映；「⭐ 重点」磁贴 1s 内出现/消失
  - 「⭐ 重点」磁贴只在有星标时出现，排第一
  - 磁贴上 CTA「▶ 练这 N 个」跳 `/practice?word_ids=...`，进入专练
  - WordDetail 抽屉顶部有「☆ 标重点 / ★ 已重点」按钮
  - Reader 底部单词面板，仅对已入库词显示星按钮
  - 删除词后，重点磁贴的计数立刻更新
  - 「重点」磁贴里的词按 wrong_count DESC, mastery ASC 排
  - 暗色 / 亮色都正常
  - 移动端排版正常
  - `npm run build` 通过

---

## 12. 不做

- 不做"用户自定义命名标签"（一词多标）—— 留作未来扩展
- 不做"批量打星"（多选词一起标）
- 不做"打星时输入备注 / 笔记"
- 不在 Practice 卡上显示星标徽章
- 不在 Dashboard 加"重点词"专门 widget
- 不做"自动打星"（如错 3 次自动标重点）—— 留作未来基于 wrong_count 的智能建议
