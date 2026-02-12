#!/usr/bin/env bash
# Install a crontab entry to run the daily summary script at 00:05
PROJECT_DIR="/Users/kawaguchishuusei/Documents/test/ai-assistant"
CRON_LINE="5 0 * * * PYTHONPATH=$PROJECT_DIR /usr/bin/env python3 $PROJECT_DIR/scripts/generate_daily_summary.py >> $PROJECT_DIR/logs/daily_summary.log 2>&1"

echo "次の crontab 行を追加します:"
echo "$CRON_LINE"
echo
read -p "crontab に追加しますか？ (y/N) " yn
if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
  # Add only if not present
  crontab -l 2>/dev/null | grep -F "$PROJECT_DIR/scripts/generate_daily_summary.py" >/dev/null 2>&1 && {
    echo "既に crontab に登録されています。"
    exit 0
  }
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "crontab に追加しました。"
else
  echo "スキップしました。手動で crontab -e から追加してください。"
fi
