#!/usr/bin/env bash
# Install and load the launchd plist for daily summary (macOS)
set -e
PROJECT_DIR="/Users/kawaguchishuusei/Documents/test/ai-assistant"
PLIST_SRC="$PROJECT_DIR/scripts/com.ai.daily-summary.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.ai.daily-summary.plist"

if [ ! -f "$PLIST_SRC" ]; then
  echo "plist が見つかりません: $PLIST_SRC"
  exit 1
fi

# Copy plist to user's LaunchAgents
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

echo "plist をコピーしました: $PLIST_DEST"

echo "次に launchctl load を実行してサービスを有効化します。管理者権限は不要です。"
echo "実行コマンド: launchctl load ~/Library/LaunchAgents/com.ai.daily-summary.plist"

echo "実行しますか？ (y/N)"
read ans
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
  launchctl unload "$PLIST_DEST" 2>/dev/null || true
  launchctl load "$PLIST_DEST"
  echo "Service loaded. ログ: $PROJECT_DIR/logs/daily_summary.log"
else
  echo "スキップしました。必要なら手動で load してください。"
fi
