#!/usr/bin/env bash
# WordGlass — one-shot install/update script for Debian/Ubuntu VPS.
#
# What it does:
#   1. Pulls latest code (or assumes you're already in the repo)
#   2. Sets up Python venv + installs backend deps
#   3. Builds frontend
#   4. Copies/links nginx + systemd configs (idempotent)
#   5. Reloads services
#
# First-time usage on a fresh VPS:
#   sudo apt update && sudo apt install -y git python3-venv python3-pip nodejs npm nginx
#   sudo useradd --system --create-home --home-dir /opt/wordglass --shell /usr/sbin/nologin wordglass
#   sudo mkdir -p /opt/wordglass && sudo chown wordglass:wordglass /opt/wordglass
#   sudo -u wordglass git clone <YOUR_REPO_URL> /opt/wordglass
#   sudo -u wordglass cp /opt/wordglass/backend/.env.example /opt/wordglass/backend/.env
#   sudo -u wordglass nano /opt/wordglass/backend/.env   # fill AI_API_KEY etc.
#   sudo bash /opt/wordglass/deploy/deploy.sh
#
# To update later:
#   cd /opt/wordglass && sudo -u wordglass git pull && sudo bash deploy/deploy.sh

set -euo pipefail

APP_DIR="/opt/wordglass"
APP_USER="wordglass"
SERVICE_NAME="wordglass-api"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

echo "==> [1/5] Preparing directories"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR/backend/data"

echo "==> [2/5] Installing backend deps"
sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet
EOF

echo "==> [3/5] Building frontend"
sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/frontend"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build
EOF

echo "==> [4/5] Installing systemd unit"
install -m 644 "$APP_DIR/deploy/wordglass-api.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null
systemctl restart "$SERVICE_NAME"

echo "==> [5/5] Installing nginx site"
NGINX_FILE="/etc/nginx/sites-available/wordglass"
if [[ ! -f "$NGINX_FILE" ]]; then
  cp "$APP_DIR/deploy/nginx.conf" "$NGINX_FILE"
  echo "    Edit $NGINX_FILE to set server_name, then re-run."
fi
ln -sf "$NGINX_FILE" /etc/nginx/sites-enabled/wordglass
nginx -t
systemctl reload nginx

echo
echo "✅ Done."
echo "   Backend:  systemctl status $SERVICE_NAME"
echo "   Logs:     journalctl -u $SERVICE_NAME -f"
echo "   Health:   curl http://127.0.0.1:8000/api/health"
