#!/usr/bin/env python3
"""Quick view of today's or latest daily summary in a readable format"""
import sys
import json
from pathlib import Path
from datetime import date, datetime
from config import Config


def format_summary(summary: dict) -> str:
    """Format summary dict into readable output"""
    lines = []
    d = summary.get('date', '----')
    lines.append(f"📅 {d}")
    lines.append("─" * 60)
    
    # Stats
    nd = summary.get('new_datasets', 0)
    ne = summary.get('new_examples', 0)
    ni = summary.get('new_indexed_documents', 0)
    ap = summary.get('approved_patches', 0)
    idx_mb = summary.get('index_size_mb', 0)
    
    lines.append(f"📚 新規データセット: {nd} 件")
    lines.append(f"📊 学習例追加: {ne} 件")
    lines.append(f"🗂️  新規インデックスドキュメント: {ni} 件")
    lines.append(f"💾 インデックスサイズ: {idx_mb:.2f} MB")
    lines.append(f"📋 承認パッチ: {ap} 件")
    
    # Learned skills
    skills = summary.get('learned_skills', [])
    if skills:
        lines.append("")
        lines.append("✨ 学習したスキル:")
        for s in skills:
            if isinstance(s, dict):
                name = s.get('name') or s.get('skill') or str(s)
            else:
                name = str(s)
            lines.append(f"  • {name}")
    
    return "\n".join(lines)


def show_latest():
    """Show latest summary"""
    summaries_dir = Config.DATA_DIR / 'summaries'
    if not summaries_dir.exists():
        print("❌ サマリディレクトリが見つかりません:", summaries_dir)
        return
    
    files = sorted(summaries_dir.glob('*.json'), reverse=True)
    if not files:
        print("❌ サマリファイルがありません")
        return
    
    with open(files[0], 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    print(format_summary(summary))


def show_for_date(d: date):
    """Show summary for specific date"""
    summaries_dir = Config.DATA_DIR / 'summaries'
    f = summaries_dir / f'{d.isoformat()}.json'
    if not f.exists():
        print(f"❌ {d.isoformat()} のサマリが見つかりません")
        return
    
    with open(f, 'r', encoding='utf-8') as fh:
        summary = json.load(fh)
    
    print(format_summary(summary))


def main():
    if len(sys.argv) > 1:
        try:
            d = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()
            show_for_date(d)
        except Exception:
            print('使い方: python3 scripts/view_daily_summary.py [YYYY-MM-DD]')
            print('        （省略時は最新のサマリを表示）')
            sys.exit(1)
    else:
        show_latest()


if __name__ == '__main__':
    main()
