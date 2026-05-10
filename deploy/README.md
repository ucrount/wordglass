# 部署到 VPS

针对 Debian 12 / Ubuntu 22+ 的 4c4g VPS。前端构建后由 nginx 直接吐静态文件，后端 uvicorn 走 systemd 常驻，nginx 反代 `/api/*`。

## 一、首次安装

```bash
# 0. 装系统依赖
sudo apt update
sudo apt install -y git python3-venv python3-pip nodejs npm nginx

# 1. 建专用用户和目录
sudo useradd --system --create-home --home-dir /opt/wordglass --shell /usr/sbin/nologin wordglass
sudo chown wordglass:wordglass /opt/wordglass

# 2. 拉代码（替换成你自己的 repo 地址）
sudo -u wordglass git clone https://github.com/<USER>/wordglass.git /opt/wordglass

# 3. 配 AI key
sudo -u wordglass cp /opt/wordglass/backend/.env.example /opt/wordglass/backend/.env
sudo -u wordglass nano /opt/wordglass/backend/.env
#    必填：AI_BASE_URL / AI_API_KEY / AI_MODEL
#    建议：把 AUTH_TOKEN 设成一个随机串（前端 localStorage 里也要存同样的）

# 4. 编辑 nginx 配置里的域名/IP
sudo nano /opt/wordglass/deploy/nginx.conf
#    把 server_name SERVER_NAME; 改成你的域名或 VPS IP

# 5. 一键部署
sudo bash /opt/wordglass/deploy/deploy.sh
```

完成后访问 `http://<你的IP或域名>` 即可。

## 二、日常更新

```bash
cd /opt/wordglass
sudo -u wordglass git pull
sudo bash deploy/deploy.sh
```

## 三、常用排查命令

```bash
# 后端日志（实时）
sudo journalctl -u wordglass-api -f

# 后端状态
sudo systemctl status wordglass-api

# 重启后端
sudo systemctl restart wordglass-api

# nginx 配置语法检查
sudo nginx -t

# 健康检查
curl http://127.0.0.1:8000/api/health
```

## 四、加 HTTPS（推荐）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

certbot 会自动改 nginx 配置加上 443 监听 + 强制跳转。

## 五、如果开了 AUTH_TOKEN

前端默认从 `localStorage["wordglass.token"]` 读 token。打开浏览器控制台一次性设：

```js
localStorage.setItem("wordglass.token", "你在 .env 里设的 AUTH_TOKEN");
```

后续所有请求会自动带 `Authorization: Bearer ...`。

## 六、备份数据库

SQLite 文件在 `/opt/wordglass/backend/data/wordglass.db`，定期 cp 到别处或 rsync 到本地即可：

```bash
# 拉到本地备份
rsync -avz user@your-vps:/opt/wordglass/backend/data/ ./wordglass-backup/
```
