# 部署到 VPS

**适用：Debian 12 / Ubuntu 22+ 的 VPS。需要 root（sudo）权限。**

## 一行命令安装

SSH 登录你的服务器，执行：

```bash
curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
```

脚本会问你 3 个问题：

1. **AI provider** — 直接回车选 `deepseek`，或输入 `openai` / `ollama` / `custom`
2. **AI_API_KEY** — 粘贴你的 key（必填）
3. **Domain or IP** — 直接回车自动用本机公网 IP，或填你的域名

之后全自动：装依赖 → 建用户 → 拉代码 → 装 Python 包 → 装 npm 包 → 编译前端 → 起 systemd → 重载 nginx。**结束时会打印访问地址和 AUTH_TOKEN**。

## 第一次访问

打开脚本最后给的地址 `http://<你的IP或域名>`。

如果脚本生成了 AUTH_TOKEN（默认会），首次进页面后按 F12 打开控制台，粘贴脚本结尾给的那一行：

```js
localStorage.setItem('wordglass.token', '....')
```

刷新页面，开始用。

## 更新代码

```bash
cd /opt/wordglass && sudo bash deploy/install.sh
```

同一个脚本，检测到已存在就只做 `git pull` + 重建 + 重启。

## 加 HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 排查

```bash
# 看后端日志
sudo journalctl -u wordglass-api -f

# 重启后端
sudo systemctl restart wordglass-api

# 健康检查
curl http://127.0.0.1:8000/api/health
```

## 备份数据库

SQLite 文件就一个：

```bash
rsync -avz user@your-vps:/opt/wordglass/backend/data/ ./wordglass-backup/
```

## 卸载

```bash
sudo systemctl disable --now wordglass-api
sudo rm /etc/systemd/system/wordglass-api.service
sudo rm /etc/nginx/sites-enabled/wordglass /etc/nginx/sites-available/wordglass
sudo systemctl reload nginx
sudo userdel -r wordglass
sudo rm -rf /opt/wordglass
```
