#!/usr/bin/env bash
# Wrapper to run daily summary generation with correct environment
PROJECT_DIR="/Users/kawaguchishuusei/Documents/test/ai-assistant"
cd "$PROJECT_DIR" || exit 1
# If you use a virtualenv, uncomment and set path below
# source /Users/kawaguchishuusei/.venv/bin/activate
PYTHONPATH="$PROJECT_DIR" /usr/bin/env python3 "$PROJECT_DIR/scripts/generate_daily_summary.py"
