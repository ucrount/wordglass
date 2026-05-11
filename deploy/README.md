# 部署到 VPS

**适用环境：** Debian 12 / Ubuntu 22+ 的 VPS，最低 1c1g（推荐 2c2g 及以上）。

---

## 一行命令安装

```bash
curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
```

脚本会**交互式问你 3 个问题**，下面分别解释。

### Q1：选 AI 服务商

```
AI provider [deepseek]:
```

输入下面之一（或回车选 `deepseek`）：

| 输入 | 自动套用 |
|---|---|
| `deepseek` ← 推荐 | `https://api.deepseek.com/v1` + `deepseek-chat` |
| `openai` | `https://api.openai.com/v1` + `gpt-4o-mini` |
| `ollama` | `http://127.0.0.1:11434/v1` + `qwen2.5:7b` |
| 其他任何值 | 进入手动模式，让你填 `AI_BASE_URL` 和 `AI_MODEL` |

> ⚠️ **不要在这一步粘 API key**。这一步只选服务商。Key 在下一步问。

### Q2：粘 API key

```
AI_API_KEY (required, paste here): sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

把 DeepSeek（或其他平台）的 API key 粘在这里。

### Q3：域名 / IP

```
Domain or IP for nginx [62.234.10.137]:
```

中括号里是脚本自动检测到的公网 IP。

- 没有域名 → 直接**回车**用 IP
- 有域名 → 输入域名（先确保 DNS A 记录已经指过来）

---

## 安装过程

脚本会按 5 个阶段跑，预计 2–5 分钟。**耐心等到 `✅ All done.` 出现再操作终端。**

```
==> [1/5] Installing system packages
==> [2/5] Preparing /opt/wordglass
    Trying fetch via direct (github.com) … / ✓ fetched via ...
==> [3/5] Configuration
==> [4/5] Building (this takes a minute on first run)
  -- pip: setting up venv + installing deps
  -- npm: installing frontend deps
  -- vite: building production bundle
==> [5/5] Starting services

✅ All done.

   🌐 Open:      http://62.234.10.137
   🔐 AUTH_TOKEN (paste in browser console once after first load):
      localStorage.setItem('wordglass.token', 'xxxxxxxxxxxx')
```

---

## 第一次访问

1. 打开脚本结尾给你的 URL，会先看到登录提示或一个空白页（因为 token 还没设）
2. 按 **F12** 打开浏览器控制台
3. 粘贴脚本给的那一行 `localStorage.setItem('wordglass.token', '...')`
4. 刷新页面，开始用 ✨

---

## 更新代码

```bash
cd /opt/wordglass && sudo bash deploy/install.sh
```

同一个脚本。第二次跑会自动检测：已存在的环境跳过初始化，只做 `git pull` + 重建 + 重启。

## 加 HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

certbot 会自动改 nginx 配置加 443 监听和强制跳转。

---

## 🔧 排查 / 常见问题

### 1. 打开网页显示 "Welcome to nginx!"

原因：`/etc/nginx/sites-enabled/wordglass` 软链没建好，或 default 没删。

修复：

```bash
sudo ln -sf /etc/nginx/sites-available/wordglass /etc/nginx/sites-enabled/wordglass
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 2. 打开网页显示 500 Internal Server Error

原因：前端没编译，`/opt/wordglass/frontend/dist/index.html` 不存在。

确认：

```bash
ls /opt/wordglass/frontend/dist/index.html
```

不存在的话重跑安装：

```bash
sudo bash /opt/wordglass/deploy/install.sh
```

留意 `==> [4/5] Building` 这一段有没有报错。

### 3. 安装报 `GnuTLS recv error` / `SSL_ERROR_SYSCALL`

国内 VPS 访问 github.com 不稳。脚本会自动 fallback 到 `ghfast.top` 等镜像，**多试几次**通常就过去了：

```bash
sudo bash /opt/wordglass/deploy/install.sh
```

如果所有镜像都不通，临时给系统配个 DNS：

```bash
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf
```

### 4. 添加单词后报 502 Bad Gateway / 报 model not found

`.env` 里 `AI_MODEL` 或 `AI_BASE_URL` 配错了。一键修成 DeepSeek 默认值：

```bash
sudo sed -i 's|^AI_BASE_URL=.*|AI_BASE_URL=https://api.deepseek.com/v1|' /opt/wordglass/backend/.env
sudo sed -i 's|^AI_MODEL=.*|AI_MODEL=deepseek-chat|' /opt/wordglass/backend/.env
sudo systemctl restart wordglass-api
```

DeepSeek 当前有效模型：`deepseek-chat`、`deepseek-reasoner`。**没有** `deepseek-v4-pro` 之类的型号。

### 5. 前端构建报 `npm ci can only install with an existing package-lock.json`

仓库现在已经提交了 `package-lock.json`。如果还报这个，先 pull 最新代码：

```bash
cd /opt/wordglass
sudo -u wordglass git pull
sudo bash deploy/install.sh
```

### 6. 装到一半卡住没反应？

`pip install` 和 `npm ci` 可能各要 1–2 分钟。脚本会实时打印进度，**只要还在输出就别打断**。如果真的卡住超过 5 分钟，Ctrl+C 后重跑（脚本是幂等的）。

### 7. 通用日志查看

```bash
# 后端实时日志
sudo journalctl -u wordglass-api -f

# nginx 错误日志
sudo tail -f /var/log/nginx/error.log

# 后端健康检查
curl http://127.0.0.1:8000/api/health
```

---

## 备份数据库

数据全在一个 SQLite 文件里：

```bash
# 服务器上拷贝
sudo cp /opt/wordglass/backend/data/wordglass.db ~/wordglass-backup-$(date +%F).db

# 或者拉到本地
rsync -avz user@your-vps:/opt/wordglass/backend/data/ ./wordglass-backup/
```

## 卸载

```bash
sudo systemctl disable --now wordglass-api
sudo rm /etc/systemd/system/wordglass-api.service
sudo rm /etc/nginx/sites-enabled/wordglass /etc/nginx/sites-available/wordglass
sudo systemctl reload nginx
sudo userdel wordglass
sudo rm -rf /opt/wordglass
```
