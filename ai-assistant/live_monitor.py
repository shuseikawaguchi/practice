"""
Live Monitor - ログストリーム監視ツール
Purpose: 放置モードのログをリアルタイムで監視・検索・フィルタリング
        - リアルタイムログストリーム
        - キーワードフィルタリング
        - ログ検索（コンテキスト付き）
        - 色分けされた表示
Usage: python3 live_monitor.py (ストリーム)
       python3 live_monitor.py tail 50 (最新50行)
       python3 live_monitor.py follow WORKER (ワーカーのみ)
       python3 live_monitor.py search ERROR (エラー検索)
Status: 放置モード稼働中に並行実行可能
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque
from config import Config

class LiveMonitor:
    """Real-time log monitor with filtering and colorization"""
    
    def __init__(self):
        self.config = Config
        self.log_file = Path(Config.LOGS_DIR) / 'ai_assistant.log'
        self.last_position = 0
        self.buffer = deque(maxlen=100)
        self.is_running = False
        
        # Color codes
        self.colors = {
            'DEBUG': '\033[36m',      # Cyan
            'INFO': '\033[32m',       # Green
            'WARNING': '\033[33m',    # Yellow
            'ERROR': '\033[31m',      # Red
            'CRITICAL': '\033[35m',   # Magenta
            'RESET': '\033[0m',
            'BOLD': '\033[1m',
            'DIM': '\033[2m',
        }
    
    def colorize_line(self, line: str) -> str:
        """Add colors to log line based on level"""
        if 'ERROR' in line.upper() or 'FAILED' in line.upper():
            return self.colors['ERROR'] + line + self.colors['RESET']
        elif 'WARNING' in line.upper():
            return self.colors['WARNING'] + line + self.colors['RESET']
        elif 'SUCCESS' in line.upper() or 'APPROVED' in line.upper():
            return self.colors['INFO'] + line + self.colors['RESET']
        elif 'DEBUG' in line.upper():
            return self.colors['DIM'] + line + self.colors['RESET']
        else:
            return line
    
    def read_new_lines(self):
        """Read new lines from log file"""
        if not self.log_file.exists():
            return []
        
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(self.last_position)
            new_lines = f.readlines()
            self.last_position = f.tell()
        
        return new_lines
    
    def filter_logs(self, lines: list, filter_text: str) -> list:
        """Filter logs by text"""
        if not filter_text:
            return lines
        
        filter_lower = filter_text.lower()
        return [line for line in lines if filter_lower in line.lower()]
    
    def print_header(self):
        """Print monitor header"""
        print('\033[2J\033[H')  # Clear screen
        print('╔' + '═' * 98 + '╗')
        print('║' + ' ' * 98 + '║')
        print('║  ' + '📊 ライブ放置モードモニタ — ログストリーム'.ljust(95) + '║')
        print('║' + ' ' * 98 + '║')
        print('╚' + '═' * 98 + '╝')
        print()
    
    def print_log_entry(self, line: str):
        """Print formatted log entry"""
        # Extract timestamp if present
        line = line.rstrip()
        
        # Truncate if too long
        if len(line) > 96:
            line = line[:93] + '...'
        
        colored_line = self.colorize_line(line)
        print(colored_line)
    
    def run_live(self, filter_text: str = '', clear_interval: int = 50):
        """Run live monitor"""
        self.is_running = True
        log_count = 0
        
        print(f'📡 接続先: {self.log_file}')
        print(f'🔍 フィルタ: {filter_text if filter_text else "なし"}')
        print(f'⏱️  開始時刻: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('─' * 100)
        print()
        
        try:
            while self.is_running:
                new_lines = self.read_new_lines()
                
                if filter_text:
                    new_lines = self.filter_logs(new_lines, filter_text)
                
                for line in new_lines:
                    self.print_log_entry(line)
                    self.buffer.append(line)
                    log_count += 1
                    
                    # Clear screen periodically to prevent scrolling lag
                    if log_count >= clear_interval:
                        self.print_header()
                        # Reprint recent logs
                        for buf_line in self.buffer:
                            self.print_log_entry(buf_line)
                        log_count = 0
                
                time.sleep(0.5)  # Check for new logs every 500ms
        
        except KeyboardInterrupt:
            print('\n\n' + '─' * 100)
            print(f'🛑 モニタ停止時刻: {datetime.now().strftime("%H:%M:%S")}')
            print(f'📈 表示したエントリ数: {log_count}')
            self.is_running = False
    
    def tail_logs(self, num_lines: int = 30):
        """Show last N lines of log"""
        if not self.log_file.exists():
            print(f'❌ ログファイルが見つかりません: {self.log_file}')
            return
        
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-num_lines:]
        
        self.print_header()
        print(f'📋 最新{num_lines}件のログ:\n')
        
        for line in lines:
            self.print_log_entry(line)
    
    def search_logs(self, pattern: str, context_lines: int = 2):
        """Search for pattern in logs"""
        if not self.log_file.exists():
            print(f'❌ ログファイルが見つかりません: {self.log_file}')
            return
        
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        self.print_header()
        print(f'🔍 検索ワード: "{pattern}"\n')
        
        matches = []
        for i, line in enumerate(lines):
            if pattern.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                matches.append((i, start, end, lines[start:end]))
        
        if not matches:
            print('該当なし。')
            return

        print(f'{len(matches)} 件見つかりました:\n')
        
        for idx, (line_num, start, end, context) in enumerate(matches):
            if idx > 0:
                print('─' * 100)

            print(f'  {self.colors["BOLD"]}マッチ #{idx + 1} (行 {start + 1}-{end}){self.colors["RESET"]}')
            print()
            
            for i, ctx_line in enumerate(context):
                actual_line_num = start + i + 1
                is_match = actual_line_num - 1 == line_num
                
                prefix = '→ ' if is_match else '  '
                color = self.colors['BOLD'] if is_match else ''
                reset = self.colors['RESET'] if is_match else ''

                print(f'{color}{prefix}{actual_line_num:5d}: {ctx_line.rstrip()}{reset}')
            print()

def main():
    monitor = LiveMonitor()
    
    if len(sys.argv) < 2:
        # Default: live stream
        monitor.run_live()
    elif sys.argv[1] == 'tail':
        # Show last N lines
        num = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        monitor.tail_logs(num)
    elif sys.argv[1] == 'follow':
        # Follow with filter
        filter_text = sys.argv[2] if len(sys.argv) > 2 else ''
        monitor.run_live(filter_text=filter_text)
    elif sys.argv[1] == 'search':
        # Search logs
        if len(sys.argv) < 3:
            print('使い方: python3 live_monitor.py search <検索ワード>')
            sys.exit(1)
        pattern = sys.argv[2]
        monitor.search_logs(pattern)
    else:
        print('使い方:')
        print('  python3 live_monitor.py               # ライブストリーム（リアルタイム表示）')
        print('  python3 live_monitor.py tail N        # 最新N行を表示（デフォルト30）')
        print('  python3 live_monitor.py follow <フィルタ>  # キーワードでフィルタ')
        print('  python3 live_monitor.py search <ワード>   # ログ検索（コンテキスト表示）')
        sys.exit(1)

if __name__ == '__main__':
    main()
