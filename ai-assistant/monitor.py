"""
Monitor Module - ワーカー監視・自動復旧デーモン
Purpose: ワーカーが正常に動作しているか監視し、問題時は自動再起動
        - プロセス監視
        - ハートビート確認
        - 自動再起動
        - ログ記録
        - エラー報告
        - バックアップ作成
Usage: python3 monitor.py
Status: 放置モード稼働時に常時監視
Note: ローカルのみで実行、外部への送信はなし
"""
import os
import time
import shutil
import logging
import subprocess
import sys
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Monitor:
    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self.stop_file = Config.STOP_FILE
        self.pid_file = Config.WORKER_PID_FILE
        self.monitor_pid_file = Config.DATA_DIR / 'monitor.pid'
        self.backup_dir = Config.BACKUP_DIR
        self.models_dir = Config.MODELS_DIR
        self.data_dir = Config.DATA_DIR

    def _is_running(self, pid_path: Path) -> bool:
        try:
            if not pid_path.exists():
                return False
            pid = int(pid_path.read_text().strip())
            # check process exists
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _restart_worker(self):
        logger.info('Attempting to restart worker...')
        # start worker in background
        cmd = [sys.executable, str(Path(__file__).parent / 'worker.py')]
        proc = subprocess.Popen(cmd)
        logger.info(f'Worker restarted with PID {proc.pid}')

    def _snapshot(self):
        ts = int(time.time())
        dst = self.backup_dir / f'snapshot_{ts}'
        dst.mkdir(parents=True, exist_ok=True)
        try:
            # copy models and data metadata (not huge binary model files unless small)
            shutil.copytree(self.models_dir, dst / 'models', dirs_exist_ok=True)
            shutil.copytree(self.data_dir, dst / 'data', dirs_exist_ok=True)
            logger.info(f'Snapshot saved to {dst}')
        except Exception as e:
            logger.error(f'Failed to snapshot: {e}')

    def run(self):
        logger.info('Monitor started')
        try:
            self.monitor_pid_file.write_text(str(os.getpid()))
        except Exception:
            pass
        while not self.stop_file.exists():
            try:
                # Check worker
                if not self._is_running(Path(Config.WORKER_PID_FILE)):
                    logger.warning('Worker not running')
                    self._restart_worker()

                # Periodic snapshot every 30 cycles (~15 minutes if poll_interval=30)
                # Use simple heuristic: snapshot if more than 30 minutes since last backup
                backups = sorted(self.backup_dir.glob('snapshot_*'))
                if not backups:
                    self._snapshot()
                else:
                    latest = backups[-1]
                    age = time.time() - int(latest.name.split('_')[-1])
                    if age > 60 * 30:
                        self._snapshot()

            except Exception as e:
                logger.error(f'Monitor loop error: {e}')
            time.sleep(self.poll_interval)
        try:
            if self.monitor_pid_file.exists():
                self.monitor_pid_file.unlink()
        except Exception:
            pass
        logger.info('Monitor stopped (STOP file found)')

if __name__ == '__main__':
    m = Monitor()
    m.run()
