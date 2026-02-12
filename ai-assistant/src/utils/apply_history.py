"""
Apply history - 適用履歴を記録/取得
"""
import json
import time
from pathlib import Path
from typing import List, Dict
from config import Config

HISTORY_FILE = Config.DATA_DIR / "apply_history.jsonl"


def add_record(record: Dict):
    record = dict(record)
    record.setdefault("ts", int(time.time()))
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def list_records(limit: int = 50) -> List[Dict]:
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    items = []
    for line in lines[-limit:]:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items
