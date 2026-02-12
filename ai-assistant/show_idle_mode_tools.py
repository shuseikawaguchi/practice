#!/usr/bin/env python3
"""
Idle Mode Visibility Quick Start
Display available monitoring tools and their usage
"""

from pathlib import Path

def main():
    print('\n' + '='*80)
    print('🔍 放置モード活動監視 - クイックスタートガイド'.center(80))
    print('='*80 + '\n')
    
    print('📊 利用可能なツール:\n')
    
    tools = [
        {
            'name': 'リアルタイムダッシュボード',
            'file': 'idle_mode_dashboard.py',
            'command': 'python3 idle_mode_dashboard.py',
            'description': '統計情報をリアルタイムで表示 (3秒毎に更新)',
        },
        {
            'name': 'ライブログストリーム',
            'file': 'live_monitor.py',
            'command': 'python3 live_monitor.py',
            'description': 'ログをリアルタイムでストリーム表示',
        },
        {
            'name': 'ワーカーのログのみ',
            'file': 'live_monitor.py',
            'command': 'python3 live_monitor.py follow WORKER',
            'description': 'ワーカーの処理をリアルタイムで追跡',
        },
        {
            'name': '最新ログ表示',
            'file': 'live_monitor.py',
            'command': 'python3 live_monitor.py tail 50',
            'description': '最後の50行のログを表示',
        },
        {
            'name': 'ログ検索',
            'file': 'live_monitor.py',
            'command': 'python3 live_monitor.py search "ERROR"',
            'description': 'エラーやキーワード検索',
        },
        {
            'name': '統合メニュービューアー',
            'file': 'view_idle_mode.py',
            'command': 'python3 view_idle_mode.py',
            'description': 'すべてのツールへのワンストップアクセス',
        },
        {
            'name': 'HTML ダッシュボード',
            'file': 'idle_mode_dashboard.py',
            'command': 'python3 idle_mode_dashboard.py --html',
            'description': 'ブラウザで見られるHTMLダッシュボード',
        },
    ]
    
    for i, tool in enumerate(tools, 1):
        print(f'{i}️⃣  {tool["name"]}')
        print(f'   📝 コマンド: {tool["command"]}')
        print(f'   💡 説明: {tool["description"]}\n')
    
    print('='*80)
    print('🚀 推奨される使い方:\n')
    
    usecases = [
        {
            'title': '全体を確認したい（推奨）',
            'command': 'python3 view_idle_mode.py',
            'description': 'メニューから好きなビューを選べます',
        },
        {
            'title': 'ワーカーの動作をリアルタイムで見たい',
            'command': 'python3 live_monitor.py follow WORKER',
            'description': 'ワーカーが何をしているかをリアルタイムで追跡',
        },
        {
            'title': 'パッチが生成されているか確認したい',
            'command': 'python3 live_monitor.py follow PATCH',
            'description': '自動パッチ生成の進捗を確認',
        },
        {
            'title': 'エラーが発生していないか確認したい',
            'command': 'python3 live_monitor.py follow ERROR',
            'description': 'エラーログをフィルタして表示',
        },
        {
            'title': '学習統計を見たい',
            'command': 'python3 idle_mode_dashboard.py',
            'description': 'ダッシュボードで学習進捗を確認',
        },
    ]
    
    for uc in usecases:
        print(f'  • {uc["title"]}')
        print(f'    → {uc["command"]}')
        print(f'    ({uc["description"]})\n')
    
    print('='*80)
    print('📚 詳細ガイド: IDLE_MODE_VISIBILITY_GUIDE.md を参照してください\n')
    
    print('⚡ 簡単な使用例:\n')
    
    examples = [
        ('python3 idle_mode_dashboard.py', 'ダッシュボード表示'),
        ('python3 live_monitor.py', 'ログストリーム開始'),
        ('python3 live_monitor.py tail 30', '最新30行表示'),
        ('python3 live_monitor.py follow WORKER', 'ワーカーログのみ'),
        ('python3 live_monitor.py search "SUCCESS"', 'SUCCESS を検索'),
        ('python3 view_idle_mode.py', '統合メニュー'),
    ]
    
    for cmd, desc in examples:
        print(f'  $ {cmd}')
        print(f'    → {desc}\n')
    
    print('='*80)
    print('✨ これで放置モードの活動が完全に可視化されます！\n')

if __name__ == '__main__':
    main()
