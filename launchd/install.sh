#!/bin/sh
# Installs (or updates) vision-ocr-server under launchd, running as the current user.
#
#   ./launchd/install.sh --host 0.0.0.0 --languages es-ES,en-US            # LaunchAgent
#   ./launchd/install.sh --daemon --host 0.0.0.0 --languages es-ES,en-US   # LaunchDaemon (sudo)
#
# LaunchAgent (default): starts when you log in. LaunchDaemon (--daemon): starts at boot with
# nobody logged in -- the choice for a headless Mac; Apple Vision works there (it needs no GUI
# session). Installing one mode removes the other. Every other argument goes to
# `vision-ocr-server` unchanged. VISION_OCR_TOKEN, if set when you run this, is written into the
# plist (optional; see the README's warning).
#
# The service gets its own self-contained install in $VISION_OCR_HOME (default
# ~/Library/vision-ocr-server): the uv tool environment, its launcher and a uv-managed Python all
# live there. Nothing the service runs depends on ~/.local/share/uv, ~/.local/bin or Homebrew's
# Python, so cleaning those (or `brew upgrade` dropping a Python version) can't break it.
set -eu
LABEL="io.github.polamatvalls91.vision-ocr-server"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
DAEMON="/Library/LaunchDaemons/$LABEL.plist"
LOG="$HOME/Library/Logs/vision-ocr-server.log"
APP="${VISION_OCR_HOME:-$HOME/Library/vision-ocr-server}"
MODE=agent
if [ "${1:-}" = "--daemon" ]; then MODE=daemon; shift; fi

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
mkdir -p "$APP" "$(dirname "$AGENT")" "$(dirname "$LOG")"
UV_TOOL_DIR="$APP/tools" UV_TOOL_BIN_DIR="$APP/bin" UV_PYTHON_INSTALL_DIR="$APP/python" \
  uv tool install --force --quiet --managed-python "$REPO"
BIN="$APP/bin/vision-ocr-server"
# Fail here, before touching the running service, if the install doesn't actually run.
"$BIN" --help >/dev/null || { echo "installed $BIN does not run" >&2; exit 1; }

# bootout returns before launchd has fully removed the job; bootstrapping too early fails with
# "Bootstrap failed: 5: Input/output error". Wait (up to 10 s) until it's gone.
wait_gone() {
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    $1 launchctl print "$2" >/dev/null 2>&1 || return 0
    sleep 0.5
  done
}

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

plist() {
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(xml "$BIN")</string>
EOF
  for arg in "$@"; do printf '    <string>%s</string>\n' "$(xml "$arg")"; done
  echo "  </array>"
  if [ "$MODE" = daemon ]; then
    printf '  <key>UserName</key><string>%s</string>\n' "$(xml "$(id -un)")"
  fi
  printf '  <key>EnvironmentVariables</key>\n  <dict>\n'
  printf '    <key>HOME</key><string>%s</string>\n' "$(xml "$HOME")"
  if [ -n "${VISION_OCR_TOKEN:-}" ]; then
    printf '    <key>VISION_OCR_TOKEN</key><string>%s</string>\n' "$(xml "$VISION_OCR_TOKEN")"
  fi
  printf '  </dict>\n'
  cat <<EOF
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$(xml "$LOG")</string>
  <key>StandardErrorPath</key><string>$(xml "$LOG")</string>
</dict>
</plist>
EOF
}

if [ "$MODE" = daemon ]; then
  TMP="$(mktemp)"
  plist "$@" > "$TMP"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$AGENT"
  sudo launchctl bootout "system/$LABEL" 2>/dev/null || true
  wait_gone sudo "system/$LABEL"
  sudo install -o root -g wheel -m 600 "$TMP" "$DAEMON"
  rm -f "$TMP"
  sudo launchctl bootstrap system "$DAEMON"
  WHERE="$DAEMON"
else
  if [ -f "$DAEMON" ]; then
    echo "A LaunchDaemon is installed ($DAEMON); remove it first:" >&2
    echo "  sudo launchctl bootout system/$LABEL && sudo rm $DAEMON" >&2
    exit 1
  fi
  plist "$@" > "$AGENT"
  chmod 600 "$AGENT"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  wait_gone "" "gui/$(id -u)/$LABEL"
  launchctl bootstrap "gui/$(id -u)" "$AGENT"
  WHERE="$AGENT"
fi

PORT=11500
prev=""
for arg in "$@"; do [ "$prev" = "--port" ] && PORT="$arg"; prev="$arg"; done
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  curl -fsS "http://127.0.0.1:$PORT/health" 2>/dev/null && { echo; echo "running ($MODE): $WHERE"; exit 0; }
  sleep 1
done
echo "not answering on port $PORT; see $LOG" >&2
exit 1
