# WordGlass

苹果毛玻璃风格的英语单词学习 web app。

> 粘个英文单词或短语 → **本地词典秒出翻译** → 五个真实例句（不用 AI 也行）→ 分类整理 → 多模式反复练习。

![tech](https://img.shields.io/badge/backend-FastAPI-009688) ![tech](https://img.shields.io/badge/frontend-Vue%203-42b883) ![tech](https://img.shields.io/badge/db-SQLite-003B57) ![tech](https://img.shields.io/badge/offline-ECDICT+Tatoeba-7c3aed) ![tech](https://img.shields.io/badge/AI-optional-412991)

---

## ✨ 功能

| 功能 | 说明 |
|---|---|
| **离线翻译** | 内置 ECDICT（77 万词条）。加单词时本地词典毫秒级返回音标 / 词性 / 中文。 |
| **离线例句** | 内置 Tatoeba 英汉对照句库。每个单词自动配 5 句由易到难的真实语料。 |
| **AI 可选** | ECDICT 没收录的生僻词或短语才会调 AI 兜底；分类、补例句都在后台异步进行，不阻塞主页响应。 |
| **单词库** | 按分类侧栏 + 搜索 + 掌握度筛选；点单词进抽屉看详情、删词、批量 🤖 AI 分类。 |
| **练习中心** | 抽认卡 + 字母槽听写 + 整句中→英 / 英→中 翻译。四档评分阶梯复习（间隔重复）。 |
| **设计** | Apple Liquid Glass：渐变背景 + 半透明卡片 + 大圆角 + 自适应明暗模式。 |
| **一键部署** | `sudo bash install.sh` 完成 git pull + 依赖 + 数据下载 + systemd + nginx，幂等可重跑。 |

---

## 🚀 部署到 VPS

一行命令（Debian / Ubuntu）：

```bash
curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
```

脚本会自动下载 ECDICT（~50MB），装完即可用，**无需配置 AI**。  
如果要 AI 兜底生僻词，装完进网页右上角 ⚙ 填一下就行。

**完整步骤 / 镜像 fallback / 排查指南** → [deploy/README.md](deploy/README.md)

---

## 📚 启用本地例句（可选）

ECDICT 不带例句，所以默认情况下例句由 AI 后台生成。要完全离线、且要例句，跑一次 Tatoeba 构建脚本：

```bash
# 在服务器上（10-20 分钟，下载 ~200MB Tatoeba 原始数据）
cd /opt/wordglass
sudo -u wordglass /opt/wordglass/backend/.venv/bin/python3 scripts/build_tatoeba.py
```

生成完 `backend/data/tatoeba.db` 后**无需重启**，后端自动识别。

---

## 💻 本地开发

**后端：**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**前端：**

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173

AI 设置在网页右上角 ⚙ 里配，不写 .env 也能跑（本地词典优先）。

---

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy · SQLite · httpx · BackgroundTasks |
| 前端 | Vue 3 · Vite · TypeScript · Vue Router |
| 离线数据 | ECDICT（词条）· Tatoeba（例句）· SQLite + FTS5 |
| AI（可选） | OpenAI 兼容（DeepSeek / OpenAI / Claude / 本地 Ollama 通吃） |
| 部署 | systemd + nginx，一键安装脚本（中国 VPS 镜像 fallback） |

## 🔑 AI 配置（可选）

完全可以**不配** AI，本地词典已经够用。要兜底生僻词，打开网页 → 右上角 ⚙ → 填 base URL / API key / model。或编辑 `backend/.env`：

```bash
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
AI_MODEL=deepseek-chat
```

## 🗺️ 路线图

- [x] **Step 1** 后端：FastAPI + SQLite + AI 客户端 + REST API
- [x] **Step 2** 前端骨架 + 毛玻璃设计系统 + Dashboard
- [x] **Step 3** 一键部署脚本（systemd + nginx + 镜像 fallback）
- [x] **Step 4** 练习中心（抽认卡 / 字母槽 / 整句翻译 + 间隔重复）
- [x] **Step 5** 单词库页（侧栏分类 + 搜索 + 掌握度筛选 + 详情抽屉）
- [x] **Step 6** 离线优先：ECDICT + Tatoeba，AI 退居可选（背景异步补分类/例句）
- [ ] 二期：TTS 听写、词根派生、统计图表、PWA、句子单独入库

## 🎨 设计

Apple Liquid Glass：渐变背景 + `backdrop-filter: blur(24px) saturate(180%)` + 半透明卡片 + 大圆角。  
核心样式见 [`frontend/src/styles/glass.css`](frontend/src/styles/glass.css)。

---

## 📜 License

MIT
