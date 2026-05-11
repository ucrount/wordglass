# WordGlass

苹果毛玻璃风格的英语单词学习 web app。

> 阅读时遇到不认识的词 → 一键保存 → AI 自动翻译+造句 → 多模式反复练习。

## 部署到 VPS（一行命令）

```bash
curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
```

详细说明见 [deploy/README.md](deploy/README.md)。

## 本地开发

**后端：**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # 编辑填入 AI_API_KEY
uvicorn app.main:app --reload --port 8000
```

**前端：**

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLite + httpx |
| 前端 | Vue 3 + Vite + TypeScript + Vue Router |
| AI | OpenAI 兼容（DeepSeek / OpenAI / Claude / Ollama 通吃） |
| 部署 | systemd + nginx |

## AI 配置

任意 OpenAI 兼容服务都行，改 `backend/.env` 三个变量即可：

```
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-...
AI_MODEL=deepseek-chat
```

## 路线图

- [x] Step 1 后端：FastAPI + SQLite + AI 客户端 + REST API
- [x] Step 2 前端骨架 + 毛玻璃设计系统 + Dashboard
- [x] Step 3 部署脚本（一键安装到 VPS）
- [ ] Step 4 单词库页（搜索 / 筛选 / 详情抽屉）
- [ ] Step 5 练习中心（仅单词 / 单词+句子 两种模式）
- [ ] 二期：TTS 听写、词根派生、统计图表、PWA

## 设计

苹果 Liquid Glass 风：渐变背景 + `backdrop-filter: blur(24px) saturate(180%)` + 半透明卡片 + 大圆角。核心样式在 `frontend/src/styles/glass.css`。
