#!/usr/bin/env bash
# WordGlass installer — handles both first install and updates.
#
# First install (run on a fresh VPS):
#   curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
#
# Update an existing install:
#   sudo bash /opt/wordglass/deploy/install.sh

set -euo pipefail

APP_DIR="/opt/wordglass"
APP_USER="wordglass"
SERVICE="wordglass-api"
REPO_URL="https://github.com/ucrount/wordglass.git"
NGINX_FILE="/etc/nginx/sites-available/wordglass"
ENV_FILE="$APP_DIR/backend/.env"

c_blue() { printf '\033[1;34m%s\033[0m\n' "$1"; }
c_green() { printf '\033[1;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$1"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

# Use /dev/tty so prompts work even when piped from curl
if [[ -t 0 ]]; then
  TTY=/dev/stdin
else
  TTY=/dev/tty
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 1 / 5 — System dependencies
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [1/5] Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3-venv python3-pip nodejs npm nginx curl openssl >/dev/null

# ──────────────────────────────────────────────────────────────────────────────
# Step 2 / 5 — Application user, directory, code
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [2/5] Preparing /opt/wordglass"
if ! id -u "$APP_USER" &>/dev/null; then
  useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  c_yellow "    Cloning repo (first install)…"
  sudo -u "$APP_USER" git clone -q "$REPO_URL" "$APP_DIR"
else
  c_yellow "    Updating repo…"
  sudo -u "$APP_USER" git -C "$APP_DIR" pull -q --ff-only
fi

install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR/backend/data"

# ──────────────────────────────────────────────────────────────────────────────
# Step 3 / 5 — Configure (.env + nginx server_name) — only first time
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [3/5] Configuration"

if [[ ! -f "$ENV_FILE" ]]; then
  echo
  echo "  Need a few things to set up the AI service."
  echo "  Common presets:  deepseek | openai | ollama  (or 'custom' to enter URL/model manually)"
  echo
  read -rp "  AI provider [deepseek]: " PRESET <"$TTY"
  PRESET=${PRESET:-deepseek}

  case "$PRESET" in
    deepseek)
      AI_BASE_URL="https://api.deepseek.com/v1"
      AI_MODEL="deepseek-chat"
      ;;
    openai)
      AI_BASE_URL="https://api.openai.com/v1"
      AI_MODEL="gpt-4o-mini"
      ;;
    ollama)
      AI_BASE_URL="http://127.0.0.1:11434/v1"
      AI_MODEL="qwen2.5:7b"
      ;;
    *)
      read -rp "  AI_BASE_URL: " AI_BASE_URL <"$TTY"
      read -rp "  AI_MODEL:    " AI_MODEL <"$TTY"
      ;;
  esac

  read -rp "  AI_API_KEY (required, paste here): " AI_API_KEY <"$TTY"
  if [[ -z "${AI_API_KEY// }" ]]; then
    echo "AI_API_KEY is required." >&2
    exit 1
  fi

  AUTH_TOKEN=$(openssl rand -hex 24)

  umask 077
  cat > "$ENV_FILE" <<EOF
AI_BASE_URL=$AI_BASE_URL
AI_API_KEY=$AI_API_KEY
AI_MODEL=$AI_MODEL
AUTH_TOKEN=$AUTH_TOKEN
DATABASE_URL=sqlite:///./data/wordglass.db
EOF
  umask 022
  chown "$APP_USER:$APP_USER" "$ENV_FILE"
  c_green "    ✓ .env written (AUTH_TOKEN auto-generated)"
fi

if [[ ! -f "$NGINX_FILE" ]]; then
  PUBLIC_IP=$(curl -fsS --max-time 4 ifconfig.me 2>/dev/null || echo "_")
  echo
  read -rp "  Domain or IP for nginx [$PUBLIC_IP]: " SERVER_NAME <"$TTY"
  SERVER_NAME=${SERVER_NAME:-$PUBLIC_IP}
  sed "s|SERVER_NAME|$SERVER_NAME|g" "$APP_DIR/deploy/nginx.conf" > "$NGINX_FILE"
  ln -sf "$NGINX_FILE" /etc/nginx/sites-enabled/wordglass
  # Disable the default site if it conflicts on port 80
  rm -f /etc/nginx/sites-enabled/default
  c_green "    ✓ nginx site configured for $SERVER_NAME"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 4 / 5 — Build backend + frontend
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [4/5] Building (this takes a minute on first run)"

sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/backend"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

cd "$APP_DIR/frontend"
if [[ ! -d node_modules ]]; then
  npm ci --silent
fi
npm run build --silent
EOF

# ──────────────────────────────────────────────────────────────────────────────
# Step 5 / 5 — Wire up systemd + nginx
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [5/5] Starting services"
install -m 644 "$APP_DIR/deploy/wordglass-api.service" "/etc/systemd/system/${SERVICE}.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"

nginx -t >/dev/null
systemctl reload nginx

# ──────────────────────────────────────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────────────────────────────────────
SERVER_NAME=$(grep -E '^\s*server_name' "$NGINX_FILE" | head -1 | awk '{print $2}' | tr -d ';')
TOKEN=$(grep '^AUTH_TOKEN=' "$ENV_FILE" | cut -d= -f2-)

echo
c_green "✅ All done."
echo
echo "   🌐 Open:        http://$SERVER_NAME"
echo "   📊 Service:     systemctl status $SERVICE"
echo "   📜 Logs:        journalctl -u $SERVICE -f"
echo
if [[ -n "$TOKEN" ]]; then
  c_yellow "   🔐 AUTH_TOKEN (paste in browser console after first load):"
  echo "      localStorage.setItem('wordglass.token', '$TOKEN')"
  echo
fi
echo "   Update later:   cd $APP_DIR && sudo bash deploy/install.sh"
