"""
Idle mode manager: start/stop monitor and worker as background processes.
Toggle via files in `data/` and by calling start_idle()/stop_idle().
"""
import os
import time
import signal
import logging
import subprocess
import sys
import re
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class IdleMode:
    def __init__(self):
        self.idle_flag = Config.DATA_DIR / 'IDLE_MODE'
        self.pid_file = Config.BASE_DIR / 'idle.pid'
        self.monitor_pid_file = Config.DATA_DIR / 'monitor.pid'
        self.worker_script = Path(__file__).parent / 'worker.py'
        self.monitor_script = Path(__file__).parent / 'monitor.py'
        self.log_dir = Config.LOGS_DIR
        self.log_dir.mkdir(exist_ok=True)

    def _start_process(self, script_path: Path, name: str):
        out = open(self.log_dir / f'{name}.out.log', 'a')
        err = open(self.log_dir / f'{name}.err.log', 'a')
        proc = subprocess.Popen([sys.executable, str(script_path)], stdout=out, stderr=err)
        logger.info(f'Started {name} (pid={proc.pid})')
        return proc.pid

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _read_pids(self):
        if not self.pid_file.exists():
            return []
        try:
            p_text = self.pid_file.read_text().strip()
        except Exception:
            return []
        pids = []
        for raw in p_text.split(','):
            raw = raw.strip()
            if not raw:
                continue
            digits = re.sub(r'\D', '', raw)
            if digits:
                try:
                    pids.append(int(digits))
                except Exception:
                    continue
        return pids

    def start_idle(self):
        if self.idle_flag.exists():
            return {'status': 'already_running'}

        # remove STOP file if present
        try:
            if Config.STOP_FILE.exists():
                Config.STOP_FILE.unlink()
        except Exception:
            pass

        # start worker and monitor
        pids = {}
        try:
            pids['worker'] = self._start_process(self.worker_script, 'worker')
        except Exception as e:
            logger.error(f'Could not start worker: {e}')
        try:
            pids['monitor'] = self._start_process(self.monitor_script, 'monitor')
        except Exception as e:
            logger.error(f'Could not start monitor: {e}')

        # write per-process pid files for dashboard
        try:
            if pids.get('monitor'):
                self.monitor_pid_file.write_text(str(pids['monitor']))
        except Exception:
            pass
        try:
            if pids.get('worker'):
                Config.WORKER_PID_FILE.write_text(str(pids['worker']))
        except Exception:
            pass

        # write idle flag and pid file
        self.idle_flag.write_text(str(int(time.time())))
        with open(self.pid_file, 'w') as f:
            f.write(','.join([str(v) for v in pids.values() if v]))

        return {'status': 'started', 'pids': pids}

    def stop_idle(self, timeout: int = 30):
        # create STOP file to signal loops to stop
        Config.STOP_FILE.write_text('stop')

        # wait for worker PID file to disappear or timeout
        waited = 0
        while waited < timeout:
            if not Config.WORKER_PID_FILE.exists():
                break
            time.sleep(1)
            waited += 1

        # attempt to kill any remaining pids from idle.pid
        try:
            if self.pid_file.exists():
                p_text = self.pid_file.read_text().strip()
                for p in p_text.split(','):
                    try:
                        pid = int(p)
                        os.kill(pid, signal.SIGTERM)
                    except Exception:
                        continue
                self.pid_file.unlink()
        except Exception as e:
            logger.error(f'Error while stopping pids: {e}')

        # remove monitor pid file
        try:
            if self.monitor_pid_file.exists():
                self.monitor_pid_file.unlink()
        except Exception:
            pass

        # remove idle flag
        try:
            if self.idle_flag.exists():
                self.idle_flag.unlink()
        except Exception:
            pass

        return {'status': 'stopped'}

    def status(self):
        running_flag = self.idle_flag.exists()
        pid_file_exists = self.pid_file.exists()
        pids = self._read_pids()
        alive_pids = [pid for pid in pids if self._pid_alive(pid)]

        status = 'not_running'
        reason = ''

        if running_flag and alive_pids:
            status = 'running'
        elif running_flag and not alive_pids:
            status = 'crashed'
            reason = 'pid_missing' if not pid_file_exists else 'pids_dead'
        elif not running_flag and alive_pids:
            status = 'running'
            reason = 'flag_missing'
        elif pid_file_exists and not alive_pids:
            status = 'stopped'
            reason = 'pid_file_stale'

        if status in {'crashed', 'stopped'}:
            try:
                if self.pid_file.exists():
                    self.pid_file.unlink()
            except Exception:
                pass
            try:
                if self.idle_flag.exists():
                    self.idle_flag.unlink()
            except Exception:
                pass

        return {
            'status': status,
            'idle': status == 'running',
            'pids': pids,
            'alive_pids': alive_pids,
            'reason': reason
        }


if __name__ == '__main__':
    im = IdleMode()
    print(im.status())
