"""
Idle Mode Dashboard - リアルタイム活動ダッシュボード
Purpose: 放置モードの AI が何をしているかをリアルタイムで可視化
        - ワーカー/モニター状態表示
        - 学習進捗グラフ
        - パッチ生成統計
        - スキル進化追跡
        - 知識ベース成長表示
Usage: python3 idle_mode_dashboard.py (3秒毎リアルタイム更新)
       python3 idle_mode_dashboard.py --html (HTML出力)
Status: 放置モード稼働中に並行実行可能
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque
import logging

from config import Config
from src.utils.daily_summary import load_recent_summaries

logger = logging.getLogger(__name__)

class IdleModeDashboard:
    """Real-time dashboard for idle mode activities"""
    
    def __init__(self):
        self.config = Config
        self.log_dir = Config.LOGS_DIR
        self.data_dir = Config.DATA_DIR
        self.refresh_interval = 2  # seconds
        self.is_running = False
        
        # Activity tracking
        self.activities = deque(maxlen=50)  # Last 50 activities
        self.load_recent_logs()
    
    def load_recent_logs(self):
        """Load recent log entries"""
        log_file = self.log_dir / 'ai_assistant.log'
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
                for line in lines:
                    if line.strip():
                        self.activities.append(line.strip())
    
    def get_worker_status(self) -> dict:
        """Get worker process status"""
        worker_pid_file = self.config.WORKER_PID_FILE
        if not worker_pid_file.exists():
            # fallback: infer from idle.pid if available
            pid = self._infer_idle_pid(index=0)
            if pid:
                return {'running': True, 'pid': pid}
            return {'running': False, 'pid': None}
        
        try:
            pid = int(worker_pid_file.read_text().strip())
            # Check if process is alive
            ret = os.system(f'kill -0 {pid} 2>/dev/null')
            return {'running': ret == 0, 'pid': pid}
        except:
            return {'running': False, 'pid': None}
    
    def get_monitor_status(self) -> dict:
        """Get monitor process status"""
        monitor_pid_file = self.config.DATA_DIR / 'monitor.pid'
        if not monitor_pid_file.exists():
            pid = self._infer_idle_pid(index=1)
            if pid:
                return {'running': True, 'pid': pid}
            return {'running': False, 'pid': None}
        
        try:
            pid = int(monitor_pid_file.read_text().strip())
            ret = os.system(f'kill -0 {pid} 2>/dev/null')
            return {'running': ret == 0, 'pid': pid}
        except:
            return {'running': False, 'pid': None}
    
    def get_learning_stats(self) -> dict:
        """Get learning statistics"""
        training_dir = self.config.TRAINING_DIR
        synthetic_files = list(training_dir.glob('synthetic_*.jsonl')) if training_dir.exists() else []
        
        # Count total examples
        total_examples = 0
        for f in synthetic_files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    total_examples += sum(1 for line in file)
            except:
                pass
        
        return {
            'synthetic_files': len(synthetic_files),
            'total_examples': total_examples,
            'latest_file': synthetic_files[-1].name if synthetic_files else 'None',
        }

    def get_dashboard_data(self) -> dict:
        """Return dashboard data as JSON-serializable dict"""
        return {
            "worker_status": self.get_worker_status(),
            "monitor_status": self.get_monitor_status(),
            "learning_stats": self.get_learning_stats(),
            "patch_stats": self.get_patch_stats(),
            "skill_stats": self.get_skill_stats(),
            "vs_stats": self.get_vector_store_stats(),
            "uptime": self.get_system_uptime(),
            "now": datetime.now().strftime("%H:%M:%S"),
            "activities": list(self.activities)[-15:],
        }

    def _infer_idle_pid(self, index: int = 0):
        """Infer worker/monitor pid from idle.pid when pid files are missing."""
        idle_pid_file = self.config.BASE_DIR / 'idle.pid'
        if not idle_pid_file.exists():
            return None
        try:
            p_text = idle_pid_file.read_text().strip()
            pids = [int(p) for p in p_text.split(',') if p.strip().isdigit()]
        except Exception:
            return None
        if index < 0 or index >= len(pids):
            return None
        pid = pids[index]
        try:
            os.kill(pid, 0)
            return pid
        except Exception:
            return None
    
    def get_patch_stats(self) -> dict:
        """Get patch proposal statistics"""
        patches_dir = self.config.DATA_DIR / 'patches'
        if not patches_dir.exists():
            return {
                'total': 0,
                'proposed': 0,
                'approved': 0,
                'failed': 0,
            }
        
        stats = {
            'total': 0,
            'proposed': 0,
            'approved': 0,
            'failed': 0,
        }
        
        for patch_dir in patches_dir.iterdir():
            if patch_dir.is_dir():
                stats['total'] += 1
                proposal_file = patch_dir / 'proposal.json'
                if proposal_file.exists():
                    try:
                        with open(proposal_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            status = data.get('status', 'unknown')
                            if status == 'PROPOSED':
                                stats['proposed'] += 1
                            elif status == 'APPROVED':
                                stats['approved'] += 1
                            elif status == 'FAILED':
                                stats['failed'] += 1
                    except:
                        pass
        
        return stats
    
    def get_skill_stats(self) -> dict:
        """Get skill statistics"""
        skills_file = self.config.DATA_DIR / 'extended_skills.json'
        if not skills_file.exists():
            return {
                'total_skills': 0,
                'expert': 0,
                'advanced': 0,
                'intermediate': 0,
                'beginner': 0,
            }
        
        try:
            with open(skills_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stats = {
                'total_skills': 0,
                'expert': 0,
                'advanced': 0,
                'intermediate': 0,
                'beginner': 0,
            }
            
            for category, skills in data.items():
                for skill, info in skills.items():
                    stats['total_skills'] += 1
                    prof = info.get('proficiency', 'Beginner')
                    stats[prof.lower()] = stats.get(prof.lower(), 0) + 1
            
            return stats
        except:
            return {
                'total_skills': 0,
                'expert': 0,
                'advanced': 0,
                'intermediate': 0,
                'beginner': 0,
            }
    
    def get_vector_store_stats(self) -> dict:
        """Get vector store statistics"""
        vs_dir = self.config.DATA_DIR / 'vector_store'
        if not vs_dir.exists():
            return {'documents': 0, 'index_size_mb': 0}
        
        doc_count = 0
        index_size = 0
        
        # Count documents
        if (vs_dir / 'documents.json').exists():
            try:
                with open(vs_dir / 'documents.json', 'r', encoding='utf-8') as f:
                    docs = json.load(f)
                    doc_count = len(docs)
            except:
                pass
        
        # Get index file size
        if (vs_dir / 'index.faiss').exists():
            index_size = (vs_dir / 'index.faiss').stat().st_size / (1024 * 1024)
        
        return {
            'documents': doc_count,
            'index_size_mb': round(index_size, 2),
        }

    def get_log_activity(self) -> dict:
        """Get recent log activity timestamps"""
        now = time.time()
        targets = {
            'ai_assistant.log': self.log_dir / 'ai_assistant.log',
            'worker.out.log': self.log_dir / 'worker.out.log',
            'worker.err.log': self.log_dir / 'worker.err.log',
            'monitor.out.log': self.log_dir / 'monitor.out.log',
            'monitor.err.log': self.log_dir / 'monitor.err.log',
        }
        activity = {}
        for name, path in targets.items():
            if path.exists():
                mtime = path.stat().st_mtime
                activity[name] = {
                    'last_update': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'age_seconds': int(now - mtime)
                }
            else:
                activity[name] = {
                    'last_update': None,
                    'age_seconds': None
                }
        return activity

    def get_health(self) -> dict:
        """Get health check summary"""
        worker = self.get_worker_status()
        monitor = self.get_monitor_status()
        idle_flag = (self.data_dir / 'IDLE_MODE').exists()
        alerts = []
        if idle_flag and not worker['running']:
            alerts.append('WORKER_NOT_RUNNING')
        if idle_flag and not monitor['running']:
            alerts.append('MONITOR_NOT_RUNNING')
        if not idle_flag:
            alerts.append('IDLE_MODE_OFF')
        return {
            'ok': len(alerts) == 0,
            'alerts': alerts,
            'idle_flag': idle_flag,
            'worker': worker,
            'monitor': monitor,
            'log_activity': self.get_log_activity(),
        }
    
    def get_system_uptime(self) -> str:
        """Get idle mode uptime"""
        idle_mode_file = self.config.DATA_DIR / 'IDLE_MODE'
        if not idle_mode_file.exists():
            return '稼働していません'
        
        try:
            timestamp = int(idle_mode_file.read_text().strip())
            start_time = datetime.fromtimestamp(timestamp)
            uptime = datetime.now() - start_time
            
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            seconds = uptime.seconds % 60
            
            return f'{hours}h {minutes}m {seconds}s'
        except:
            return '不明'
    
    def print_dashboard(self):
        """Print formatted dashboard"""
        os.system('clear' if os.name == 'posix' else 'cls')
        
        worker_status = self.get_worker_status()
        monitor_status = self.get_monitor_status()
        learning_stats = self.get_learning_stats()
        patch_stats = self.get_patch_stats()
        skill_stats = self.get_skill_stats()
        vs_stats = self.get_vector_store_stats()
        uptime = self.get_system_uptime()
        
        # Header
        print('╔' + '═' * 78 + '╗')
        print('║' + ' ' * 78 + '║')
        print('║  ' + '🚀 AI 放置モード ダッシュボード — リアルタイム活動モニタ'.ljust(75) + '║')
        print('║' + ' ' * 78 + '║')
        print('╚' + '═' * 78 + '╝')
        
        # Status
        print(f'\n⏱️  稼働時間: {uptime}')
        print(f'📅 現在時刻: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        
        # Process Status
        print('\n┌─ プロセス状況 ' + '─' * 62 + '┐')
        worker_icon = '✅' if worker_status['running'] else '❌'
        monitor_icon = '✅' if monitor_status['running'] else '❌'
        print(f'│ {worker_icon} ワーカー (PID {worker_status["pid"]}): {"稼働中" if worker_status["running"] else "停止"}')
        print(f'│ {monitor_icon} モニタ (PID {monitor_status["pid"]}): {"稼働中" if monitor_status["running"] else "停止"}')
        print('└' + '─' * 78 + '┘')
        
        # Learning Progress
        print('\n┌─ 学習状況 ' + '─' * 58 + '┐')
        print(f'│ 📚 合成データセット: {learning_stats["synthetic_files"]} 件')
        print(f'│ 📊 学習例: {learning_stats["total_examples"]} 件')
        print(f'│ 📝 最新データセット: {learning_stats["latest_file"]}')
        print('└' + '─' * 78 + '┘')
        
        # Vector Store
        print('\n┌─ 知識ベース ' + '─' * 62 + '┐')
        print(f'│ 🗂️  インデックス済ドキュメント: {vs_stats["documents"]} 件')
        print(f'│ 💾 インデックスサイズ: {vs_stats["index_size_mb"]:.2f} MB')
        print('└' + '─' * 78 + '┘')
        
        # Patches
        print('\n┌─ 自動パッチ生成 ' + '─' * 54 + '┐')
        print(f'│ 📋 提案総数: {patch_stats["total"]}')
        print(f'│ ⏳ 保留（提案中）: {patch_stats["proposed"]}')
        print(f'│ 🆗 承認済: {patch_stats["approved"]}')
        print(f'│ ❌ 失敗: {patch_stats["failed"]}')
        print('└' + '─' * 78 + '┘')
        
        # Skills
        print('\n┌─ スキル進化 ' + '─' * 61 + '┐')
        print(f'│ 📚 スキル総数: {skill_stats["total_skills"]}')
        print(f'│ 🏆 上級: {skill_stats["expert"]} | ⭐ 中上級: {skill_stats["advanced"]} | ✨ 中堅: {skill_stats["intermediate"]} | 📖 初級: {skill_stats["beginner"]}')
        print('└' + '─' * 78 + '┘')
        
        # Recent Activities
        print('\n┌─ 最近の活動（最新10件） ' + '─' * 47 + '┐')
        recent_activities = list(self.activities)[-10:]
        for activity in recent_activities:
            # Truncate long lines
            if len(activity) > 75:
                activity = activity[:72] + '...'
            print(f'│ {activity:<76} │')
        print('└' + '─' * 78 + '┘')

        # Daily Summaries (past 7 days)
        summaries = load_recent_summaries(days=7)
        print('\n┌─ 日次サマリ（過去7日） ' + '─' * 54 + '┐')
        if not summaries:
            print('│ (サマリはまだありません)'.ljust(78) + ' │')
        else:
            for s in summaries:
                date_str = s.get('date', '----')
                nd = s.get('new_datasets', 0)
                ne = s.get('new_examples', 0)
                ni = s.get('new_indexed_documents', 0)
                ap = s.get('approved_patches', 0)
                line = f'│ {date_str}: データセット +{nd} / 学習例 +{ne} / インデックス +{ni} / 承認パッチ +{ap}'
                if len(line) > 78:
                    line = line[:75] + '...'
                print(f"{line.ljust(78)} │")
        print('└' + '─' * 78 + '┘')

        # Detailed summaries with skills (latest 3 days)
        print('\n┌─ 詳細サマリ（最新3日） ' + '─' * 54 + '┐')
        if not summaries:
            print('│ (サマリはまだありません)'.ljust(78) + ' │')
        else:
            for idx, s in enumerate(summaries[:3]):
                date_str = s.get('date', '----')
                nd = s.get('new_datasets', 0)
                ne = s.get('new_examples', 0)
                ni = s.get('new_indexed_documents', 0)
                ap = s.get('approved_patches', 0)
                skill_count = s.get('learned_skills_count', 0)
                skills = s.get('learned_skills', [])
                
                # Header
                print(f'│ {date_str}:'.ljust(78) + ' │')
                print(f'│   📊 データセット +{nd} | 学習例 +{ne} | インデックス +{ni} | パッチ +{ap}'.ljust(78) + ' │')
                
                # Skills
                if skill_count > 0:
                    print(f'│   ✨ 学習スキル: {skill_count} 件'.ljust(78) + ' │')
                    for skill in skills[:3]:  # Show first 3 skills
                        skill_name = skill if isinstance(skill, str) else str(skill)[:50]
                        print(f'│     • {skill_name}'.ljust(78) + ' │')
                    if skill_count > 3:
                        print(f'│     ... 他 {skill_count - 3} 件'.ljust(78) + ' │')
                
                if idx < min(2, len(summaries) - 1):
                    print('│ ' + '─' * 76 + ' │')
        print('└' + '─' * 78 + '┘')
        
        # Footer
        print('\n💡 ヒント: Ctrl+Cで監視を停止します')
        print('⚙️  設定: ENABLE_AUTOMATED_EVOLUTION =', Config.ENABLE_AUTOMATED_EVOLUTION)
    
    def run_live(self, interval: int = 60):
        """Run live dashboard with auto-refresh"""
        self.is_running = True
        try:
            while self.is_running:
                self.load_recent_logs()
                self.print_dashboard()
                print(f'\n🔄 {interval}秒後に更新します... (Ctrl+Cで停止)')
                time.sleep(interval)
        except KeyboardInterrupt:
            print('\n\n👋 ダッシュボードを停止しました。')
            self.is_running = False
    
    def get_html_dashboard(self) -> str:
        """Generate HTML dashboard for web view"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>放置モード ダッシュボード</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Monaco', 'Courier New', monospace;
            background: #0a0e27;
            color: #e0e6ed;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            color: #00d9ff;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .card {{
            background: #1a1f3a;
            border: 2px solid #00d9ff;
            border-radius: 8px;
            padding: 20px;
        }}
        .card h3 {{
            color: #00d9ff;
            margin-bottom: 15px;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        .stat {{
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            font-size: 13px;
        }}
        .stat-label {{ color: #888; }}
        .stat-value {{ color: #00ff88; font-weight: bold; }}
        .status-running {{ color: #00ff88; }}
        .status-stopped {{ color: #ff4444; }}
        .progress-bar {{
            background: #0f1525;
            height: 20px;
            border-radius: 4px;
            margin: 8px 0;
            overflow: hidden;
        }}
        .progress-fill {{
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-size: 11px;
            font-weight: bold;
        }}
        .activities {{
            background: #1a1f3a;
            border: 2px solid #00d9ff;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }}
        .activity-item {{
            padding: 8px;
            margin: 4px 0;
            background: #0f1525;
            border-left: 3px solid #00d9ff;
            border-radius: 4px;
            font-size: 12px;
            overflow-x: auto;
        }}
        .refresh-info {{
            text-align: center;
            margin-top: 20px;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 AI 放置モード ダッシュボード</h1>
        
        <div class="grid">
            <div class="card">
                <h3>⏱️ ステータス</h3>
                <div class="stat">
                    <span class="stat-label">稼働時間:</span>
                    <span class="stat-value" id="uptime">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">現在時刻:</span>
                    <span class="stat-value" id="now">--</span>
                </div>
            </div>
            
            <div class="card">
                <h3>🔧 プロセス</h3>
                <div class="stat">
                    <span class="stat-label">Worker:</span>
                    <span class="stat-value" id="workerStatus">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Monitor:</span>
                    <span class="stat-value" id="monitorStatus">--</span>
                </div>
            </div>
            
            <div class="card">
                <h3>📚 学習</h3>
                <div class="stat">
                    <span class="stat-label">データセット数:</span>
                    <span class="stat-value" id="syntheticFiles">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">学習例数:</span>
                    <span class="stat-value" id="totalExamples">--</span>
                </div>
            </div>
            
            <div class="card">
                <h3>🗂️ 知識ベース</h3>
                <div class="stat">
                    <span class="stat-label">ドキュメント数:</span>
                    <span class="stat-value" id="docCount">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">インデックスサイズ:</span>
                    <span class="stat-value" id="indexSize">--</span>
                </div>
            </div>
            
            <div class="card">
                <h3>📋 パッチ</h3>
                <div class="stat">
                    <span class="stat-label">提案総数:</span>
                    <span class="stat-value" id="patchTotal">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">保留（提案中）:</span>
                    <span class="stat-value" id="patchProposed">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">承認済:</span>
                    <span class="stat-value" id="patchApproved">--</span>
                </div>
            </div>
            
            <div class="card">
                <h3>📚 スキル</h3>
                <div class="stat">
                    <span class="stat-label">合計:</span>
                    <span class="stat-value" id="skillTotal">--</span>
                </div>
                <div class="stat">
                    <span class="stat-label">上級:</span>
                    <span class="stat-value" id="skillExpert">--</span>
                </div>
            </div>
        </div>
        
        <div class="activities">
            <h3>📊 最近の活動</h3>
            <div id="activities"></div>
        </div>
        
        <div class="refresh-info">🔄 5秒ごとに自動更新中...</div>
    </div>
    
    <script>
        function byId(id){{ return document.getElementById(id); }}
        function setStatus(el, running){{
            el.className = 'stat-value ' + (running ? 'status-running' : 'status-stopped');
            el.textContent = running ? '✅ 稼働中' : '❌ 停止';
        }}
        function render(data){{
            if (!data) return;
            byId('uptime').textContent = data.uptime || '--';
            byId('now').textContent = data.now || '--';
            setStatus(byId('workerStatus'), data.worker_status && data.worker_status.running);
            setStatus(byId('monitorStatus'), data.monitor_status && data.monitor_status.running);
            byId('syntheticFiles').textContent = (data.learning_stats && data.learning_stats.synthetic_files) || 0;
            byId('totalExamples').textContent = (data.learning_stats && data.learning_stats.total_examples) || 0;
            byId('docCount').textContent = (data.vs_stats && data.vs_stats.documents) || 0;
            byId('indexSize').textContent = (data.vs_stats && data.vs_stats.index_size_mb !== undefined) ? (data.vs_stats.index_size_mb.toFixed(2) + ' MB') : '--';
            byId('patchTotal').textContent = (data.patch_stats && data.patch_stats.total) || 0;
            byId('patchProposed').textContent = (data.patch_stats && data.patch_stats.proposed) || 0;
            byId('patchApproved').textContent = (data.patch_stats && data.patch_stats.approved) || 0;
            byId('skillTotal').textContent = (data.skill_stats && data.skill_stats.total_skills) || 0;
            byId('skillExpert').textContent = (data.skill_stats && data.skill_stats.expert) || 0;
            var act = byId('activities');
            var items = data.activities || [];
            var html = '';
            for (var i=0;i<items.length;i++){{
                html += '<div class="activity-item">' + items[i] + '</div>';
            }}
            act.innerHTML = html || '<div class="activity-item">（活動なし）</div>';
        }}
        function fetchData(){{
            var xhr = new XMLHttpRequest();
            xhr.open('GET','/api/dashboard/data');
            xhr.onload = function(){{
                if (xhr.status === 200){{
                    try {{ render(JSON.parse(xhr.responseText)); }} catch(e) {{}}
                }}
            }};
            xhr.send();
        }}
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
        """
        return html

if __name__ == '__main__':
    dashboard = IdleModeDashboard()

    if len(sys.argv) > 1 and sys.argv[1] == '--html':
        # Generate HTML and save
        html = dashboard.get_html_dashboard()
        html_file = Path('/tmp/idle_dashboard.html')
        html_file.write_text(html)
        print(f'✅ ダッシュボードを保存しました: {html_file}')
        print(f'ブラウザで開く: file://{html_file}')
    else:
        # Run live dashboard
        dashboard.run_live(interval=60)
