#!/usr/bin/env python3
"""Check idle mode and self-learning status"""

from idle_mode import IdleMode
from config import Config
from patch_validator import PatchValidator
import os

print('=' * 70)
print('🔍 放置モード & 自己学習システム 状態確認')
print('=' * 70)

# 1. IdleMode 状態確認
print('\n1️⃣  放置モード状態')
print('-' * 70)
im = IdleMode()
status = im.status()
print(f'📊 状態: {status}')

# 2. ファイル確認
idle_mode_file = Config.DATA_DIR / 'IDLE_MODE'
idle_pid_file = Config.DATA_DIR / 'idle.pid'

print('\n2️⃣  ファイル確認')
print('-' * 70)
print(f'IDLE_MODE ファイル: {"✅ 存在" if idle_mode_file.exists() else "❌ 無し"}')
if idle_mode_file.exists():
    content = idle_mode_file.read_text().strip()
    print(f'  内容: {content}')

print(f'idle.pid ファイル: {"✅ 存在" if idle_pid_file.exists() else "❌ 無し"}')
if idle_pid_file.exists():
    pid_content = idle_pid_file.read_text().strip()
    print(f'  内容: {pid_content}')

# 3. プロセス確認
print('\n3️⃣  バックグラウンドプロセス')
print('-' * 70)
worker_pid_file = Config.WORKER_PID_FILE

if worker_pid_file.exists():
    wpid = int(worker_pid_file.read_text().strip())
    print(f'Worker PID ファイル: ✅ 存在')
    print(f'  Worker PID: {wpid}')
    # Check if process is alive
    ret = os.system(f'kill -0 {wpid} 2>/dev/null')
    if ret == 0:
        print(f'  ✅ Worker プロセス実行中')
    else:
        print(f'  ❌ Worker プロセス停止中')
else:
    print(f'Worker PID ファイル: ❌ 無し')
    print(f'  ⚠️  Worker が起動していません')

# 4. 自動進化設定確認
print('\n4️⃣  自動進化設定')
print('-' * 70)
print(f'ENABLE_AUTOMATED_EVOLUTION: {Config.ENABLE_AUTOMATED_EVOLUTION}')
if Config.ENABLE_AUTOMATED_EVOLUTION:
    print('  ✅ 自動進化が有効です')
else:
    print('  ⚠️  自動進化は無効です（手動承認が必要）')

# 5. Training/Synthetic データ確認
print('\n5️⃣  学習データ')
print('-' * 70)
training_dir = Config.TRAINING_DIR
if training_dir.exists():
    synthetic_files = list(training_dir.glob('synthetic_*.jsonl'))
    synthetic_count = len(synthetic_files)
    print(f'Training ディレクトリ: ✅ 存在')
    print(f'  Synthetic データファイル数: {synthetic_count}')
    if synthetic_count > 0:
        print(f'  最新: {synthetic_files[-1].name}')
else:
    print(f'Training ディレクトリ: ❌ 無し')
    print(f'  Synthetic データ: 0')

# 6. パッチ提案確認
print('\n6️⃣  自動生成パッチ提案')
print('-' * 70)
proposals = PatchValidator.list_proposals()
print(f'総提案数: {len(proposals)}')
if proposals:
    for p in proposals:
        status_icon = '🆗' if p['status'] == 'APPROVED' else '⏳' if p['status'] == 'PROPOSED' else '❌'
        print(f'  {status_icon} {p["id"]}: {p["title"]} [{p["status"]}]')
else:
    print('  パッチなし')

# 7. STOP ファイル確認
print('\n7️⃣  停止フラグ')
print('-' * 70)
stop_file = Config.STOP_FILE
if stop_file.exists():
    print(f'STOP ファイル: ✅ 存在')
    print(f'  ⚠️  放置モードは停止予定です')
else:
    print(f'STOP ファイル: ❌ 無し')
    print(f'  ✅ 放置モードは継続中です')

# Summary
print('\n' + '=' * 70)
print('📋 サマリー')
print('=' * 70)

idle_running = idle_mode_file.exists() and not stop_file.exists()
if idle_running:
    print('✅ 放置モード: オン')
    print('✅ 自己学習: 実行中')
    if Config.ENABLE_AUTOMATED_EVOLUTION:
        print('✅ 自動進化: 有効')
    else:
        print('⚠️  自動進化: 無効（手動承認モード）')
    if synthetic_count > 0:
        print(f'✅ 学習データ: {synthetic_count} ファイル')
else:
    print('❌ 放置モード: オフ')
    print('❌ 自己学習: 停止中')

print('=' * 70)
