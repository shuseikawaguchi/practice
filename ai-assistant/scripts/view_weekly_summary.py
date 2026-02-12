#!/usr/bin/env python3
"""Weekly summary statistics view"""
import json
from pathlib import Path
from datetime import date, timedelta
from config import Config


def main():
    summaries_dir = Config.DATA_DIR / 'summaries'
    if not summaries_dir.exists():
        print("❌ サマリディレクトリが見つかりません")
        return
    
    files = sorted(summaries_dir.glob('*.json'), reverse=True)[:7]
    if not files:
        print("❌ サマリファイルがありません")
        return
    
    print("\n📊 週間学習統計（過去7日）")
    print("=" * 60)
    
    totals = {
        'datasets': 0,
        'examples': 0,
        'documents': 0,
        'patches': 0,
        'skills': 0,
    }
    
    for f in reversed(files):
        with open(f, 'r', encoding='utf-8') as fh:
            s = json.load(fh)
        
        date_str = s.get('date', '----')
        nd = s.get('new_datasets', 0)
        ne = s.get('new_examples', 0)
        ni = s.get('new_indexed_documents', 0)
        ap = s.get('approved_patches', 0)
        sk = s.get('learned_skills_count', 0)
        
        totals['datasets'] += nd
        totals['examples'] += ne
        totals['documents'] += ni
        totals['patches'] += ap
        totals['skills'] += sk
        
        print(f"{date_str} | 📚 {nd:2d} | 📊 {ne:2d} | 🗂️  {ni:2d} | 📋 {ap:2d} | ✨ {sk:2d}")
    
    print("=" * 60)
    print(f"合計      | 📚 {totals['datasets']:2d} | 📊 {totals['examples']:2d} | 🗂️  {totals['documents']:2d} | 📋 {totals['patches']:2d} | ✨ {totals['skills']:2d}")
    print()


if __name__ == '__main__':
    main()
