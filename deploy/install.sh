#!/usr/bin/env bash
# WordGlass installer — handles both first install and updates.
# Tolerant of flaky GitHub access via mirror fallback (helps on China VPS).
#
# First install:
#   curl -fsSL https://raw.githubusercontent.com/ucrount/wordglass/main/deploy/install.sh | sudo bash
#
# Update:
#   sudo bash /opt/wordglass/deploy/install.sh

set -euo pipefail

APP_DIR="/opt/wordglass"
APP_USER="wordglass"
SERVICE="wordglass-api"
REPO_URL="https://github.com/ucrount/wordglass.git"
NGINX_FILE="/etc/nginx/sites-available/wordglass"
ENV_FILE="$APP_DIR/backend/.env"

# Mirror prefixes tried in order if direct github.com is blocked/slow.
GIT_MIRRORS=("" "https://ghfast.top/" "https://gh-proxy.com/" "https://ghps.cc/")

# Faster pip / npm sources (work globally, dramatically faster from CN).
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
NPM_REGISTRY="https://registry.npmmirror.com"

c_blue()   { printf '\033[1;34m%s\033[0m\n' "$1"; }
c_green()  { printf '\033[1;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$1"; }
c_red()    { printf '\033[1;31m%s\033[0m\n' "$1"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

TTY=/dev/tty
[[ -t 0 ]] && TTY=/dev/stdin

# ──────────────────────────────────────────────────────────────────────────────
# Step 1 / 5 — System dependencies
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [1/5] Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3-venv python3-pip nodejs npm nginx curl openssl ca-certificates >/dev/null

# ──────────────────────────────────────────────────────────────────────────────
# Git helpers — try direct, then mirrors
# ──────────────────────────────────────────────────────────────────────────────
# Per-attempt timeout. A direct github.com TCP connection on a CN VPS can hang
# silently for many minutes — we'd rather bail in 20s and try the next mirror.
GIT_TIMEOUT=20

configure_git_tolerance() {
  # If a transfer drops below 1 KB/s for 10s, give up so the next mirror is tried.
  sudo -u "$APP_USER" git config --global http.postBuffer 524288000 || true
  sudo -u "$APP_USER" git config --global http.lowSpeedLimit 1000 || true
  sudo -u "$APP_USER" git config --global http.lowSpeedTime 10 || true
}

# Run git as APP_USER with a hard wall-clock timeout and no credential prompts.
run_git() {
  sudo -u "$APP_USER" \
    env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/true \
    timeout --foreground "$GIT_TIMEOUT" git "$@"
}

git_clone_robust() {
  for prefix in "${GIT_MIRRORS[@]}"; do
    local url="${prefix}${REPO_URL}"
    local label="${prefix:-direct (github.com)}"
    c_yellow "    Trying clone via $label (≤${GIT_TIMEOUT}s) …"
    if run_git clone -q "$url" "$APP_DIR"; then
      [[ -n "$prefix" ]] && run_git -C "$APP_DIR" remote set-url origin "$url"
      c_green "    ✓ cloned via $label"
      return 0
    fi
    c_yellow "    × $label failed/timed out, trying next…"
  done
  return 1
}

git_fetch_robust() {
  for prefix in "${GIT_MIRRORS[@]}"; do
    local url="${prefix}${REPO_URL}"
    local label="${prefix:-direct (github.com)}"
    c_yellow "    Trying fetch via $label (≤${GIT_TIMEOUT}s) …"
    if run_git -C "$APP_DIR" remote get-url origin &>/dev/null; then
      run_git -C "$APP_DIR" remote set-url origin "$url"
    else
      run_git -C "$APP_DIR" remote add origin "$url"
    fi
    if run_git -C "$APP_DIR" fetch -q origin; then
      c_green "    ✓ fetched via $label"
      return 0
    fi
    c_yellow "    × $label failed/timed out, trying next…"
  done
  return 1
}

# ──────────────────────────────────────────────────────────────────────────────
# Step 2 / 5 — Application user, directory, code
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [2/5] Preparing $APP_DIR"
if ! id -u "$APP_USER" &>/dev/null; then
  useradd --system --no-create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

configure_git_tolerance

if [[ -d "$APP_DIR/.git" ]]; then
  if ! git_fetch_robust; then
    c_red "    All git sources failed. Check VPS network / DNS / firewall."
    exit 1
  fi
  sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard -q origin/main
elif [[ -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]]; then
  c_yellow "    Adopting non-empty $APP_DIR …"
  sudo -u "$APP_USER" git -C "$APP_DIR" init -q -b main
  if ! git_fetch_robust; then
    c_red "    All git sources failed. Check VPS network / DNS / firewall."
    exit 1
  fi
  sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard -q origin/main
  sudo -u "$APP_USER" git -C "$APP_DIR" branch --set-upstream-to=origin/main main 2>/dev/null || true
else
  if ! git_clone_robust; then
    c_red "    All git sources failed. Check VPS network / DNS / firewall."
    exit 1
  fi
fi

install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR/backend/data"

# ──────────────────────────────────────────────────────────────────────────────
# Step 3 / 5 — Configure + offline dictionaries
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [3/5] Configuration"

if [[ ! -f "$ENV_FILE" ]]; then
  echo
  echo "  AI 服务可以在网页里配置（推荐），也可以现在就填到 .env 里。"
  echo "  直接回车跳过 → 装完后打开网页右上角 ⚙ 设置即可。"
  echo
  read -rp "  现在配置 AI? (y/N): " CONFIGURE_NOW <"$TTY"
  CONFIGURE_NOW=${CONFIGURE_NOW:-n}

  AI_BASE_URL=""
  AI_API_KEY=""
  AI_MODEL=""

  if [[ "$CONFIGURE_NOW" =~ ^[Yy] ]]; then
    echo "  Common presets:  deepseek | openai | ollama   (or 'custom' for manual entry)"
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
    read -rp "  AI_API_KEY: " AI_API_KEY <"$TTY"
  fi

  umask 077
  cat > "$ENV_FILE" <<EOF
AI_BASE_URL=$AI_BASE_URL
AI_API_KEY=$AI_API_KEY
AI_MODEL=$AI_MODEL
AUTH_TOKEN=
DATABASE_URL=sqlite:///./data/wordglass.db
EOF
  umask 022
  chown "$APP_USER:$APP_USER" "$ENV_FILE"
  c_green "    ✓ .env written (you can edit AI settings later in the web UI)"
fi

if [[ ! -f "$NGINX_FILE" ]]; then
  PUBLIC_IP=$(curl -fsS --max-time 4 ifconfig.me 2>/dev/null || echo "_")
  echo
  read -rp "  Domain or IP for nginx [$PUBLIC_IP]: " SERVER_NAME <"$TTY"
  SERVER_NAME=${SERVER_NAME:-$PUBLIC_IP}
  sed "s|SERVER_NAME|$SERVER_NAME|g" "$APP_DIR/deploy/nginx.conf" > "$NGINX_FILE"
  c_green "    ✓ nginx site file created for $SERVER_NAME"
else
  # On updates: refresh nginx config from repo so the user picks up changes
  # (e.g. SSE buffering fixes). Preserve the existing server_name.
  EXISTING_NAME=$(grep -E '^\s*server_name' "$NGINX_FILE" | head -1 | awk '{print $2}' | tr -d ';')
  if [[ -n "$EXISTING_NAME" ]]; then
    sed "s|SERVER_NAME|$EXISTING_NAME|g" "$APP_DIR/deploy/nginx.conf" > "$NGINX_FILE"
    c_green "    ✓ nginx site file refreshed (server_name preserved: $EXISTING_NAME)"
  fi
fi

# Always (re)ensure the site is enabled and default is gone — idempotent.
ln -sf "$NGINX_FILE" /etc/nginx/sites-enabled/wordglass
rm -f /etc/nginx/sites-enabled/default

# ──────────────────────────────────────────────────────────────────────────────
# Offline dictionary data — ECDICT (required for offline lookup) + Tatoeba
# (optional, used for example sentences when AI is not configured).
# Both are downloaded once and left alone on subsequent runs.
# ──────────────────────────────────────────────────────────────────────────────
ECDICT_DB="$APP_DIR/backend/data/ecdict.db"
TATOEBA_DB="$APP_DIR/backend/data/tatoeba.db"

# ECDICT — official release ships a zipped sqlite file.
ECDICT_URL_BASE="https://github.com/skywind3000/ECDICT/releases/download/1.0.28/ecdict-sqlite-28.zip"
# Tatoeba — built via scripts/build_tatoeba.py and uploaded to our own release.
# Edit this tag/URL after uploading. If the URL 404s we silently skip.
TATOEBA_URL_BASE="https://github.com/ucrount/wordglass/releases/download/data-v1/tatoeba.db.bz2"

# Try downloading $1 (a github URL) into $2, racing through GIT_MIRRORS prefixes.
download_github() {
  local base_url="$1"
  local out="$2"
  for prefix in "${GIT_MIRRORS[@]}"; do
    local url="${prefix}${base_url}"
    local label="${prefix:-direct (github.com)}"
    if curl -fsSL --max-time 180 --retry 1 -o "$out.part" "$url"; then
      mv "$out.part" "$out"
      c_green "    ✓ downloaded via $label"
      return 0
    fi
    rm -f "$out.part"
    c_yellow "    × $label failed, trying next…"
  done
  return 1
}

if [[ ! -f "$ECDICT_DB" ]]; then
  c_blue "==> Fetching ECDICT (offline English↔Chinese dictionary, ~50MB zipped)"
  TMP_ZIP="/tmp/ecdict-$$.zip"
  if download_github "$ECDICT_URL_BASE" "$TMP_ZIP"; then
    apt-get install -y -qq unzip >/dev/null 2>&1 || true
    unzip -o -q "$TMP_ZIP" -d "$APP_DIR/backend/data/"
    rm -f "$TMP_ZIP"
    # The zip extracts a .db file whose name varies across versions
    # (ecdict.db / stardict.db). Pick the largest .db that isn't ours.
    if [[ ! -f "$ECDICT_DB" ]]; then
      CAND=$(find "$APP_DIR/backend/data" -maxdepth 1 -name '*.db' \
              ! -name 'wordglass.db' ! -name 'tatoeba.db' \
              -printf '%s %p\n' 2>/dev/null | sort -rn | head -1 | awk '{print $2}')
      if [[ -n "$CAND" ]]; then mv "$CAND" "$ECDICT_DB"; fi
    fi
    chown "$APP_USER:$APP_USER" "$ECDICT_DB" 2>/dev/null || true
    c_green "    ✓ ECDICT ready at $ECDICT_DB"
  else
    c_yellow "    ! ECDICT download failed — offline lookup will be disabled. App still works if AI is configured."
  fi
else
  c_green "✓ ECDICT already present, skipping download"
fi

if [[ ! -f "$TATOEBA_DB" ]]; then
  c_blue "==> Fetching Tatoeba example sentences (optional, ~40MB)"
  TMP_BZ="/tmp/tatoeba-$$.db.bz2"
  if download_github "$TATOEBA_URL_BASE" "$TMP_BZ"; then
    bunzip2 -f "$TMP_BZ"
    mv "${TMP_BZ%.bz2}" "$TATOEBA_DB"
    chown "$APP_USER:$APP_USER" "$TATOEBA_DB" 2>/dev/null || true
    c_green "    ✓ Tatoeba ready at $TATOEBA_DB"
  else
    rm -f "$TMP_BZ"
    c_yellow "    ! Tatoeba release asset not available — example sentences in offline mode disabled."
    c_yellow "      To enable: run scripts/build_tatoeba.py locally, upload the resulting"
    c_yellow "      tatoeba.db.bz2 to a GitHub release, and update TATOEBA_URL_BASE in this script."
  fi
else
  c_green "✓ Tatoeba already present, skipping download"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Step 4 / 5 — Build backend + frontend (using fast mirrors)
# ──────────────────────────────────────────────────────────────────────────────
c_blue "==> [4/5] Building (this takes a minute on first run)"

sudo -u "$APP_USER" bash <<EOF
set -e
cd "$APP_DIR/backend"
echo "  -- pip: setting up venv + installing deps"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip -i $PIP_INDEX
.venv/bin/pip install -r requirements.txt -i $PIP_INDEX

cd "$APP_DIR/frontend"
if [[ ! -d node_modules ]]; then
  echo "  -- npm: installing frontend deps (first time, ~1-2 min)"
  npm ci --registry=$NPM_REGISTRY --no-audit --no-fund --loglevel=warn
fi
echo "  -- vite: building production bundle"
npm run build
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

echo
c_green "✅ All done."
echo
echo "   🌐 Open:      http://$SERVER_NAME"
echo "   📊 Service:   systemctl status $SERVICE"
echo "   📜 Logs:      journalctl -u $SERVICE -f"
echo
c_yellow "   ⚙  First time? Open the URL above, then go to the gear icon"
c_yellow "      (top-right) to configure AI provider / model / API key."
echo
echo "   Update later: cd $APP_DIR && sudo bash deploy/install.sh"
