"""
FileManager - 自動ファイル配置ユーティリティ
Purpose: AIやシステムが自動生成するファイルを機能別フォルダへ整理して保存する
Features:
 - コンポーネント名から保存先ディレクトリを解決
 - 必要に応じてディレクトリを作成
 - ファイルを書き込み、既存ファイルのバックアップを作成
 - 簡易的なshim作成支援（エントリポイント維持）

Usage:
 from config import Config
 from src.utils.file_manager import FileManager
 fm = FileManager()
 path = fm.write_component_file('patches', 'proposal.json', json_text)
"""
from pathlib import Path
import shutil
import time
import json

from config import Config

class FileManager:
    def __init__(self):
        self.map = Config.AUTO_FILE_MAP

    def get_component_dir(self, component: str) -> Path:
        """Resolve and return the directory Path for a given component."""
        return self.map.get(component, Config.BASE_DIR)

    def ensure_dir(self, component: str) -> Path:
        """Ensure the component directory exists and return it."""
        d = self.get_component_dir(component)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_component_file(self, component: str, filename: str, content: str, backup: bool = True) -> Path:
        """Write content to filename under the component directory.

        If backup is True and file exists, rename the existing file with a timestamp suffix.
        Returns the Path to the written file.
        """
        d = self.ensure_dir(component)
        p = d / filename
        if backup and p.exists():
            ts = int(time.time())
            b = p.with_name(f"{p.stem}.bak.{ts}{p.suffix}")
            shutil.move(str(p), str(b))
        # Ensure parent exists
        p.parent.mkdir(parents=True, exist_ok=True)
        # Write
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        p.write_text(content, encoding='utf-8')
        return p

    def create_shim(self, component: str, module_path: str, shim_name: str = None) -> Path:
        """Create a small shim file at project root that imports the moved module.

        Example: create_shim('core', 'src.core.worker', 'worker.py') will
        create top-level 'worker.py' shim that imports and runs src.core.worker.
        """
        shim_name = shim_name or f"{component}.py"
        shim_path = Config.BASE_DIR / shim_name
        target = module_path
        shim_code = f"""
# Shim: redirects to module in src
from {module_path.rsplit('.',1)[0]} import {module_path.rsplit('.',1)[1]}

if __name__ == '__main__':
    # If module defines a main-style entry, call it
    try:
        {module_path.rsplit('.',1)[1]}.main()
    except AttributeError:
        try:
            {module_path.rsplit('.',1)[1]}.start()
        except AttributeError:
            print('Shim executed. Use the src module directly.')
"""
        shim_path.write_text(shim_code, encoding='utf-8')
        return shim_path

# Simple convenience instance
_default_file_manager = FileManager()

def write_component_file(component: str, filename: str, content: str, backup: bool = True) -> Path:
    return _default_file_manager.write_component_file(component, filename, content, backup)
