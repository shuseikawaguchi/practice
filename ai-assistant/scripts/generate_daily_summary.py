#!/usr/bin/env python3
"""Generate daily learning summary (usage: python3 scripts/generate_daily_summary.py [YYYY-MM-DD])"""
import sys
from datetime import datetime, date
from src.utils.daily_summary import generate_summary_for_date


def main():
    if len(sys.argv) > 1:
        try:
            d = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
        except Exception:
            print('使い方: python3 scripts/generate_daily_summary.py [YYYY-MM-DD]')
            return
    else:
        d = date.today()

    out = generate_summary_for_date(d)
    print(f'✅ 日次サマリを生成しました: {out}')


if __name__ == '__main__':
    main()
