#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
elif [[ -f "venv/bin/activate" ]]; then
  source venv/bin/activate
else
  echo "[ERROR] Python仮想環境が見つかりません (.venv または venv)"
  exit 1
fi

export AI_ASSISTANT_API_RELOAD=1
export AI_ASSISTANT_API_HOST="${AI_ASSISTANT_API_HOST:-0.0.0.0}"
export AI_ASSISTANT_API_PORT="${AI_ASSISTANT_API_PORT:-8000}"

echo "[INFO] Starting API with auto-reload: http://${AI_ASSISTANT_API_HOST}:${AI_ASSISTANT_API_PORT}/ui"
echo "[INFO] ファイル更新時に自動で再起動されます（手動再起動不要）"
python api.py
