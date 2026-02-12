#!/usr/bin/env python3
"""Show learned skills from memory file.
Usage: python3 scripts/show_learned_skills.py [YYYY-MM-DD]
If date omitted, shows all learned skills (and timestamps if available).
"""
import sys
from datetime import datetime
from pathlib import Path
import json
from config import Config


def parse_ts(val):
    try:
        return float(val)
    except Exception:
        try:
            return datetime.fromisoformat(val).timestamp()
        except Exception:
            return None


def show_for_date(d=None):
    mem = {}
    mf = Config.MEMORY_FILE
    if not mf.exists():
        print('メモリファイルが存在しません:', mf)
        return

    with open(mf, 'r', encoding='utf-8') as f:
        mem = json.load(f)

    skills = mem.get('learned_skills', []) if isinstance(mem, dict) else []
    if d is None:
        print(f'学習済スキル（合計 {len(skills)} 件）:')
        for s in skills:
            print('-', s)
        return

    start_ts = datetime.combine(d, datetime.min.time()).timestamp()
    end_ts = start_ts + 86400
    filtered = []
    for s in skills:
        ts = None
        if isinstance(s, dict):
            for k in ('learned_at', 'added_at', 'timestamp', 'time'):
                if k in s:
                    ts = parse_ts(s.get(k))
                    break
        if ts and start_ts <= ts < end_ts:
            filtered.append(s)

    print(f'{d.isoformat()} に学習したスキル: {len(filtered)} 件')
    for s in filtered:
        print('-', s)


def main():
    d = None
    if len(sys.argv) > 1:
        try:
            d = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except Exception:
            print('使い方: python3 scripts/show_learned_skills.py [YYYY-MM-DD]')
            return

    show_for_date(d)


if __name__ == '__main__':
    main()
