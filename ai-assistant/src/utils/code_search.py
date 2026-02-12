"""
Code search - リポジトリ内の簡易検索
"""
from pathlib import Path
from typing import List, Dict
from config import Config

DEFAULT_EXTS = [".py", ".md", ".txt", ".json", ".yml", ".yaml"]
DEFAULT_IGNORE_DIRS = {".git", ".venv", "__pycache__", "data", "models", "logs", "backups"}


def search_code(query: str, max_files: int = 200, max_matches: int = 50, exts: List[str] = None) -> Dict:
    if not query:
        return {"query": query, "matches": []}
    exts = exts or DEFAULT_EXTS
    matches = []
    files_scanned = 0

    for path in Config.BASE_DIR.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix.lower() not in exts:
            continue
        if any(part in DEFAULT_IGNORE_DIRS for part in path.parts):
            continue
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if query.lower() in line.lower():
                matches.append({"file": str(path), "line": i, "text": line.strip()[:300]})
                if len(matches) >= max_matches:
                    return {"query": query, "matches": matches, "files_scanned": files_scanned}
        if max_files and files_scanned >= max_files:
            break

    return {"query": query, "matches": matches, "files_scanned": files_scanned}
