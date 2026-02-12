#!/usr/bin/env python3
"""Show aggregate summary across all available daily summaries."""
import json
from pathlib import Path
from config import Config


def main():
    summaries_dir = Config.DATA_DIR / 'summaries'
    if not summaries_dir.exists():
        print("❌ サマリディレクトリが見つかりません:", summaries_dir)
        return

    files = sorted(summaries_dir.glob('*.json'))
    if not files:
        print("❌ サマリファイルがありません")
        return

    totals = {
        'datasets': 0,
        'examples': 0,
        'documents': 0,
        'patches': 0,
        'skills': 0,
    }
    dates = []

    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                s = json.load(fh)
            dates.append(s.get('date') or f.stem)
            totals['datasets'] += int(s.get('new_datasets', 0) or 0)
            totals['examples'] += int(s.get('new_examples', 0) or 0)
            totals['documents'] += int(s.get('new_indexed_documents', 0) or 0)
            totals['patches'] += int(s.get('approved_patches', 0) or 0)
            totals['skills'] += int(s.get('learned_skills_count', 0) or 0)
        except Exception:
            continue

    start_date = dates[0] if dates else '----'
    end_date = dates[-1] if dates else '----'

    print("\n📌 全期間サマリ（全ファイル集計）")
    print("=" * 60)
    print(f"期間: {start_date} 〜 {end_date}（{len(files)} 日分）")
    print(f"📚 新規データセット合計: {totals['datasets']} 件")
    print(f"📊 学習例追加合計: {totals['examples']} 件")
    print(f"🗂️  新規インデックスドキュメント合計: {totals['documents']} 件")
    print(f"📋 承認パッチ合計: {totals['patches']} 件")
    print(f"✨ 学習スキル合計: {totals['skills']} 件")
    print("=" * 60)
    print()


if __name__ == '__main__':
    main()
