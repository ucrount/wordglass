# 部署到 VPS

**适用环境：** Debian 12 / Ubuntu 22+ 的 VPS，最低 1c1g（推荐 2c2g 及以上）。  
**新装机预估：** 5-8 分钟，含 ECDICT 下载。

---

## 一行命令安装

```bash
curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
```

脚本是**幂等**的——同一条命令既能用来初次安装，也能用来日常更新。  
中国 VPS 自动用 `ghfast.top` 等镜像 fallback，并给每次 git 操作加了 20s 硬超时，不会卡死。

### 装完后

打开脚本结尾给你的 URL（http://你的IP），主页直接可用：

- ✅ **不需要配置 AI**：内置 ECDICT 词典，加单词就有翻译/音标/词性
- ✅ **不需要配置 AI**：主页下方"阅读 & 翻译"面板里，点任意单词都能立刻查词
- 💡 **可选**：右上角 ⚙ 填 AI 配置，可以处理 ECDICT 没收录的生僻词、自动分类、补例句、**翻译整段文本**

---

## 交互问题（一次性）

脚本第一次安装时会问 3 个问题，更新时**全部跳过**。

### Q1：现在配置 AI?  (y/N)

**直接回车跳过即可**，本地词典已经够用。要配的话脚本会接着问：

| 输入 | 自动套用 |
|---|---|
| `deepseek` ← 推荐 | `https://api.deepseek.com/v1` + `deepseek-chat` |
| `openai` | `https://api.openai.com/v1` + `gpt-4o-mini` |
| `ollama` | `http://127.0.0.1:11434/v1` + `qwen2.5:7b` |
| 其他任何值 | 手动模式，让你填 `AI_BASE_URL` / `AI_MODEL` |

随后会让你粘 API key。

### Q2：域名 / IP for nginx

```
Domain or IP for nginx [62.234.10.137]:
```

中括号里是脚本自动检测到的公网 IP。

- 没有域名 → 直接**回车**用 IP
- 有域名 → 输入域名（先确保 DNS A 记录已指过来）

---

## 安装阶段

```
==> [1/5] Installing system packages
==> [2/5] Preparing /opt/wordglass
    Trying fetch via direct (github.com) (≤20s)…
    × direct (github.com) failed/timed out, trying next…
    Trying fetch via https://ghfast.top/ (≤20s)…
    ✓ fetched via https://ghfast.top/
==> [3/5] Configuration
==> Fetching ECDICT (offline English↔Chinese dictionary, ~50MB zipped)
    ✓ ECDICT ready at /opt/wordglass/backend/data/ecdict.db
==> Fetching Tatoeba example sentences (optional, ~40MB)
    ! Tatoeba release asset not available — example sentences in offline mode disabled.
==> [4/5] Building (this takes a minute on first run)
==> [5/5] Starting services

✅ All done.
```

**预计 5-8 分钟。耐心等到 `✅ All done.` 出现再操作终端。**

---

## 启用本地例句（可选）

ECDICT 不带例句库。要让加单词时立刻显示 5 个本地例句（完全离线、零 AI 调用），跑一次 Tatoeba 构建脚本：

```bash
cd /opt/wordglass
sudo -u wordglass /opt/wordglass/backend/.venv/bin/python3 scripts/build_tatoeba.py
```

预计 10-20 分钟（看你 VPS 的国际带宽）：

- 下载 sentences.tar.bz2 + links.tar.bz2，合计约 200MB（含**断点续传**）
- 处理输出 `backend/data/tatoeba.db`（约 30-80MB）
- 内存峰值约 300-500MB

担心 SSH 断线就用 nohup：

```bash
sudo -u wordglass nohup /opt/wordglass/backend/.venv/bin/python3 \
  /opt/wordglass/scripts/build_tatoeba.py > /tmp/tatoeba.log 2>&1 &
tail -f /tmp/tatoeba.log
```

跑完后**无需重启**，后端自动识别 `tatoeba.db` 并启用本地例句。

---

## 第一次访问

1. 打开脚本结尾给你的 URL
2. 主页直接可以加单词；要 AI 兜底/分类的话，右上角 ⚙ 配 AI

如果你设置了 `AUTH_TOKEN`（默认空），还要在浏览器控制台执行一次：

```js
localStorage.setItem('wordglass.token', '<你的 token>')
```

---

## 更新代码

```bash
sudo bash /opt/wordglass/deploy/install.sh
```

同一个脚本。会做：

1. git pull（带 20s 超时 + 镜像 fallback）
2. 跳过已存在的 .env / nginx 配置
3. 检查 ECDICT 是否存在，缺了才重新下
4. 重建后端依赖 + 前端构建
5. 重启 systemd 服务、重载 nginx

## 加 HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

certbot 会自动改 nginx 配置加 443 监听 + 强制跳转。

---

## 🔧 排查 / 常见问题

### 1. git pull 卡在 `Trying fetch via direct (github.com)…`

旧版 install.sh 没超时控制，国内 VPS 会一直挂。最新版每次尝试 20 秒就 fallback，**应该不会再有这个问题**。如果你还是从旧版升级，先手动拉一次最新代码：

```bash
sudo -u wordglass git -C /opt/wordglass remote set-url origin \
  https://ghfast.top/https://github.com/ucrount/wordglass.git
sudo -u wordglass git -C /opt/wordglass fetch origin
sudo -u wordglass git -C /opt/wordglass reset --hard origin/main
sudo bash /opt/wordglass/deploy/install.sh
```

### 2. 打开网页显示 "Welcome to nginx!"

```bash
sudo ln -sf /etc/nginx/sites-available/wordglass /etc/nginx/sites-enabled/wordglass
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 3. 打开网页显示 500 Internal Server Error

前端没编译，`/opt/wordglass/frontend/dist/index.html` 不存在。重跑：

```bash
sudo bash /opt/wordglass/deploy/install.sh
```

### 4. ECDICT 下载失败

脚本会自动重试镜像。如果所有镜像都不通：

```bash
# 临时改 DNS
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
sudo bash /opt/wordglass/deploy/install.sh
```

实在不行可以本地下载好后手动放到 `/opt/wordglass/backend/data/ecdict.db`，下次跑脚本会跳过。

### 5. 添加单词后没反应 / 报 502

**没配 AI 也应该能用**——ECDICT 词典覆盖了大部分常见词。如果是生僻词或短语，需要 AI 兜底：

- 右上角 ⚙ 检查 AI 配置
- DeepSeek 当前有效模型：`deepseek-chat`、`deepseek-reasoner`
- 改完点 "测试" 确认连得通

或者命令行强制改成默认 DeepSeek：

```bash
sudo sed -i 's|^AI_BASE_URL=.*|AI_BASE_URL=https://api.deepseek.com/v1|' /opt/wordglass/backend/.env
sudo sed -i 's|^AI_MODEL=.*|AI_MODEL=deepseek-chat|' /opt/wordglass/backend/.env
sudo systemctl restart wordglass-api
```

### 6. 加单词很慢

如果每次加单词都要等 1-3 秒，说明 ECDICT 没装好（或者输入的是 ECDICT 没收录的词，AI 同步兜底）。检查：

```bash
ls -lh /opt/wordglass/backend/data/ecdict.db
# 应该看到 ~135MB 的文件
```

不存在的话重跑 install.sh，留意 `==> Fetching ECDICT` 那一段。

### 7. 例句要等几秒才出现

正常——本地 Tatoeba 没装的话，例句靠后台 AI 异步生成，1-5 秒后前端会自动刷出来（Dashboard 会轮询）。要彻底秒出，跑一次 `scripts/build_tatoeba.py`。

### 8. 通用日志

```bash
# 后端实时日志
sudo journalctl -u wordglass-api -f

# nginx 错误日志
sudo tail -f /var/log/nginx/error.log

# 后端健康检查
curl http://127.0.0.1:8000/api/health

# 本地离线词典状态
curl http://127.0.0.1:8000/api/words/offline-status
# {"ecdict": true, "tatoeba": false}
```

---

## 备份数据

数据全在 SQLite 文件里：

```bash
# 用户数据（必须备份）
sudo cp /opt/wordglass/backend/data/wordglass.db ~/wordglass-backup-$(date +%F).db

# 拉到本地
rsync -avz user@your-vps:/opt/wordglass/backend/data/wordglass.db ./
```

`ecdict.db` 和 `tatoeba.db` 不用备份——install.sh 或 `build_tatoeba.py` 能随时重建。

## 卸载

```bash
sudo systemctl disable --now wordglass-api
sudo rm /etc/systemd/system/wordglass-api.service
sudo rm /etc/nginx/sites-enabled/wordglass /etc/nginx/sites-available/wordglass
sudo systemctl reload nginx
sudo userdel wordglass
sudo rm -rf /opt/wordglass
```
