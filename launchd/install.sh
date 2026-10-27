#!/bin/sh
# Installs (or updates) vision-ocr-server as a LaunchAgent of the logged-in user.
# Apple Vision needs a user session, so this is a LaunchAgent, not a LaunchDaemon.
#
#   ./launchd/install.sh --host 0.0.0.0 --languages es-ES,en-US
#
# Every argument goes to `vision-ocr-server` unchanged. VISION_OCR_TOKEN, if set when you run
# this, is written into the agent (optional; see the README's warning).
set -eu
LABEL="io.github.polamatvalls91.vision-ocr-server"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/vision-ocr-server.log"

command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
uv tool install --force --quiet "$REPO"
BIN="$(uv tool dir --bin)/vision-ocr-server"

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

{
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
  if [ -n "${VISION_OCR_TOKEN:-}" ]; then
    printf '  <key>EnvironmentVariables</key>\n  <dict><key>VISION_OCR_TOKEN</key><string>%s</string></dict>\n' \
      "$(xml "$VISION_OCR_TOKEN")"
  fi
  cat <<EOF
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$(xml "$LOG")</string>
  <key>StandardErrorPath</key><string>$(xml "$LOG")</string>
</dict>
</plist>
EOF
} > "$PLIST"
chmod 600 "$PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

PORT=11500
prev=""
for arg in "$@"; do [ "$prev" = "--port" ] && PORT="$arg"; prev="$arg"; done
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -fsS "http://127.0.0.1:$PORT/health" 2>/dev/null && { echo; echo "running: $PLIST"; exit 0; }
  sleep 1
done
echo "not answering on port $PORT; see $LOG" >&2
exit 1
