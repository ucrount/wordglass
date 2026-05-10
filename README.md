# WordGlass

苹果毛玻璃风格的单词学习 web app。MVP 阶段：保存单词 → AI 自动翻译+造句 → 练习。

## 一期范围

- ✅ 后端：FastAPI + SQLite + OpenAI 兼容 AI 客户端
- ✅ 前端骨架 + 毛玻璃设计系统
- ✅ Dashboard：添加单词、统计、最近列表
- ⏳ 单词库页（Step 3）
- ⏳ 练习中心（Step 4）
- ⏳ 部署脚本（Step 5）

## 本地启动

### 后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入你的 AI_BASE_URL / AI_API_KEY / AI_MODEL
uvicorn app.main:app --reload --port 8000
```

健康检查：`curl http://127.0.0.1:8000/api/health` → `{"ok":true}`

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173

## AI 配置示例

任意 OpenAI 兼容服务都行：

```
# DeepSeek
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-...
AI_MODEL=deepseek-chat

# OpenAI
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini

# 本地 Ollama (无需 key)
AI_BASE_URL=http://127.0.0.1:11434/v1
AI_API_KEY=ollama
AI_MODEL=qwen2.5:7b
```

## 简介

- 数据库：SQLite，文件在 `backend/data/wordglass.db`
- 复习算法：阶梯式 — `0d / 1d / 3d / 7d / 21d / 60d`，详见 `app/review.py`
- 鉴权：`AUTH_TOKEN` 留空 = 全开（本地开发用）；线上部署请填随机串
