"""
Repository indexer - リポジトリを索引化してRAGに反映
"""
from pathlib import Path
from typing import List, Iterable, Optional
import logging
from config import Config
from vector_store import VectorStore

logger = logging.getLogger(__name__)

DEFAULT_EXTS = [".py", ".md", ".txt", ".json", ".yml", ".yaml"]
DEFAULT_IGNORE_DIRS = {".git", ".venv", "__pycache__", "data", "models", "logs", "backups"}


def _iter_files(base_dir: Path, exts: List[str], max_files: int) -> Iterable[Path]:
    count = 0
    for path in base_dir.rglob("*"):
        if path.is_dir():
            if path.name in DEFAULT_IGNORE_DIRS:
                # Skip entire ignored dir
                for _ in []:
                    pass
            continue
        if path.suffix.lower() not in exts:
            continue
        if any(part in DEFAULT_IGNORE_DIRS for part in path.parts):
            continue
        yield path
        count += 1
        if max_files and count >= max_files:
            break


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    if chunk_size <= 0:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def index_repository(
    base_dir: Optional[Path] = None,
    exts: Optional[List[str]] = None,
    max_files: int = 500,
    chunk_size: int = 2000,
    overlap: int = 200,
) -> dict:
    base_dir = base_dir or Config.BASE_DIR
    exts = exts or DEFAULT_EXTS

    vs = VectorStore()
    files = list(_iter_files(base_dir, exts, max_files))
    added = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not text.strip():
            continue
        for idx, chunk in enumerate(_chunk_text(text, chunk_size=chunk_size, overlap=overlap)):
            doc_id = f"{path}:{idx}"
            vs.add(doc_id, chunk, metadata={"source": str(path), "chunk": idx})
            added += 1

    if added == 0:
        return {"indexed_files": len(files), "chunks": 0}

    vs.build()
    vs.save()
    logger.info(f"Indexed {len(files)} files, {added} chunks")
    return {"indexed_files": len(files), "chunks": added}
