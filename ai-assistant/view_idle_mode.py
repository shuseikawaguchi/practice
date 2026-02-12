#!/usr/bin/env python3
"""
View Idle Mode - 統合ダッシュボード・メニュービューアー
Purpose: 全ての監視・ダッシュボード機能へのワンストップアクセス
        - ダッシュボード表示
        - ログストリーム
        - フィルタ検索
        - HTMLダッシュボード出力
Usage: python3 view_idle_mode.py (日本語メニューから選択)
Status: 放置モード稼働中に並行実行可能
"""

import sys
import subprocess
from pathlib import Path

def show_menu():
    """Show main menu"""
    print('\n╔' + '═' * 78 + '╗')
    print('║' + ' ' * 78 + '║')
    print('║  ' + '📊 IDLE MODE ACTIVITY VIEWER'.ljust(75) + '║')
    print('║' + ' ' * 78 + '║')
    print('╚' + '═' * 78 + '╝')
    print()
    print('オプション:')
    print()
    print('  1️⃣  リアルタイムダッシュボード (1分毎に更新)')
    print('  2️⃣  ライブログストリーム (全てのログをリアルタイム表示)')
    print('  3️⃣  最新ログ表示 (最後の30行)')
    print('  4️⃣  ワーカーのログのみ (フィルタ済み)')
    print('  5️⃣  トレーナーのログのみ (フィルタ済み)')
    print('  6️⃣  パッチのログのみ (フィルタ済み)')
    print('  7️⃣  ログ検索 (キーワード検索)')
    print('  8️⃣  HTML ダッシュボード (ブラウザで表示)')
    print('  9️⃣  日次サマリ（最新）を表示')
    print('  🔟  週次サマリ（過去7日）を表示')
    print('  1️⃣1️⃣  全期間サマリを表示')
    print('  0️⃣  終了')
    print()

def run_command(cmd, explanation=''):
    """Run a command"""
    if explanation:
        print(f'\n{explanation}...\n')
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        print('\n\n✋ キャンセルしました')
    except Exception as e:
        print(f'❌ エラー: {e}')

def main():
    ai_dir = Path(__file__).parent
    
    while True:
        show_menu()
        choice = input('選択: ').strip()
        
        if choice == '1':
            run_command(
                f'cd {ai_dir} && python3 idle_mode_dashboard.py',
                '📊 リアルタイムダッシュボードを起動中'
            )
        
        elif choice == '2':
            run_command(
                f'cd {ai_dir} && python3 live_monitor.py',
                '📡 ライブログストリームを開始中'
            )
        
        elif choice == '3':
            run_command(
                f'cd {ai_dir} && python3 live_monitor.py tail 30',
                '📋 最新ログを表示中'
            )
        
        elif choice == '4':
            run_command(
                f'cd {ai_dir} && python3 live_monitor.py follow WORKER',
                '🔍 ワーカーのログをフィルタ中'
            )
        
        elif choice == '5':
            run_command(
                f'cd {ai_dir} && python3 live_monitor.py follow TRAINER',
                '🔍 トレーナーのログをフィルタ中'
            )
        
        elif choice == '6':
            run_command(
                f'cd {ai_dir} && python3 live_monitor.py follow PATCH',
                '🔍 パッチのログをフィルタ中'
            )
        
        elif choice == '7':
            keyword = input('検索キーワード: ').strip()
            if keyword:
                run_command(
                    f'cd {ai_dir} && python3 live_monitor.py search "{keyword}"',
                    f'🔍 "{keyword}" を検索中'
                )
        
        elif choice == '8':
            run_command(
                f'cd {ai_dir} && python3 idle_mode_dashboard.py --html && open /tmp/idle_dashboard.html',
                '🌐 HTML ダッシュボードを生成・表示中'
            )

        elif choice == '9':
            run_command(
                f'cd {ai_dir} && PYTHONPATH={ai_dir} python3 scripts/view_daily_summary.py',
                '📅 日次サマリ（最新）を表示中'
            )

        elif choice == '10':
            run_command(
                f'cd {ai_dir} && PYTHONPATH={ai_dir} python3 scripts/view_weekly_summary.py',
                '📊 週次サマリ（過去7日）を表示中'
            )

        elif choice == '11':
            run_command(
                f'cd {ai_dir} && PYTHONPATH={ai_dir} python3 scripts/view_all_summaries.py',
                '📌 全期間サマリを表示中'
            )
        
        elif choice == '0':
            print('\n👋 終了します\n')
            break
        
        else:
            print('❌ 無効な選択です')

if __name__ == '__main__':
    main()
