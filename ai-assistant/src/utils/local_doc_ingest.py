"""
Local document ingestion with optional OCR for image files.
"""
import json
import time
import hashlib
import logging
from pathlib import Path

from config import Config
from vector_store import VectorStore
from src.utils.provider_selector import select_provider

logger = logging.getLogger(__name__)


def load_local_docs_state() -> dict:
    try:
        if Config.LOCAL_DOC_INGEST_STATE_FILE.exists():
            return json.loads(Config.LOCAL_DOC_INGEST_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _save_local_docs_state(added: int, scanned: int):
    try:
        state = {
            "last_run": time.time(),
            "added": int(added),
            "scanned": int(scanned),
        }
        Config.LOCAL_DOC_INGEST_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def ocr_image_file(path: Path) -> str:
    try:
        provider = select_provider("ocr", "tesseract")
        if provider != "tesseract":
            logger.warning(f"[OCR] Provider '{provider}' not available; falling back to tesseract")
        try:
            from PIL import Image, ImageOps
        except Exception:
            logger.warning("[OCR] Pillow not installed; skipping image")
            return ""
        try:
            import pytesseract
        except Exception:
            logger.warning("[OCR] pytesseract not installed; skipping image")
            return ""

        img = Image.open(path)
        try:
            img = img.convert("RGB")
        except Exception:
            pass

        try:
            # grayscale + autocontrast for OCR
            gray = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(gray)
        except Exception:
            pass

        try:
            width, height = img.size
            max_pixels = int(getattr(Config, "OCR_MAX_PIXELS", 0) or 0)
            min_width = int(getattr(Config, "OCR_UPSCALE_MIN_WIDTH", 0) or 0)
            if min_width and width < min_width:
                scale = float(min_width) / float(max(1, width))
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(new_size)
            if max_pixels and (width * height) > max_pixels:
                scale = (max_pixels / float(width * height)) ** 0.5
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(new_size)
        except Exception:
            pass

        lang = getattr(Config, "OCR_LANG", "eng") or "eng"
        tess_config = getattr(Config, "OCR_TESS_CONFIG", "") or ""
        try:
            text = pytesseract.image_to_string(img, lang=lang, config=tess_config)
        except Exception:
            try:
                text = pytesseract.image_to_string(img, lang="eng", config=tess_config)
            except Exception as e:
                logger.warning(f"[OCR] Failed for {path}: {e}")
                return ""
        return (text or "").strip()
    except Exception as e:
        logger.warning(f"[OCR] Error for {path}: {e}")
        return ""


def process_image_for_learning(path: Path, rebuild: bool = True) -> dict:
    try:
        text = ocr_image_file(path)
        if not text:
            return {"ok": False, "reason": "empty_text"}
        clean_dir = Config.DATA_DIR / "clean"
        clean_dir.mkdir(parents=True, exist_ok=True)
        doc_id = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
        out = clean_dir / f"local_{doc_id}.txt"
        out.write_text(text, encoding="utf-8")
        result = {"ok": True, "text": text, "clean_file": str(out)}
        if rebuild:
            result["vector_store"] = build_vector_store_from_clean()
        return result
    except Exception as e:
        logger.warning(f"[OCR] Failed to process image {path}: {e}")
        return {"ok": False, "error": str(e)}


def _load_watch_state() -> dict:
    try:
        if Config.OCR_WATCH_STATE_FILE.exists():
            return json.loads(Config.OCR_WATCH_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _save_watch_state(state: dict):
    try:
        Config.OCR_WATCH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def ingest_images_from_dirs(dirs, rebuild: bool = False) -> dict:
    img_exts = set([e.lower() for e in (getattr(Config, "OCR_IMAGE_EXTS", []) or [])])
    state = _load_watch_state()
    processed = 0
    added = 0
    for d in (dirs or []):
        base = Path(d)
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_dir():
                continue
            if p.suffix.lower() not in img_exts:
                continue
            key = str(p.resolve())
            mtime = p.stat().st_mtime
            if state.get(key) and state.get(key) >= mtime:
                continue
            processed += 1
            result = process_image_for_learning(p, rebuild=False)
            if result.get("ok"):
                added += 1
                state[key] = mtime
    if processed:
        _save_watch_state(state)
    if rebuild and added:
        build_vector_store_from_clean()
    return {"processed": processed, "added": added}


def ingest_local_docs_to_clean(force: bool = False) -> dict:
    try:
        min_interval = int(Config.LOCAL_DOC_INGEST_MIN_INTERVAL_SECONDS or 0)
        if min_interval > 0 and not force:
            state = load_local_docs_state()
            last_run = float(state.get("last_run") or 0)
            remaining = min_interval - (time.time() - last_run)
            if remaining > 0:
                logger.info("[LOCAL] ⏭️  Skipping local docs ingest (cooldown)")
                return {
                    "skipped": True,
                    "reason": "cooldown",
                    "remaining_seconds": int(remaining),
                    "state": state,
                }

        clean_dir = Config.DATA_DIR / "clean"
        clean_dir.mkdir(parents=True, exist_ok=True)
        exts = set([e.lower() for e in (Config.LOCAL_DOC_EXTS or [])])
        img_exts = set([e.lower() for e in (getattr(Config, "OCR_IMAGE_EXTS", []) or [])])
        exclude_dirs = set(Config.LOCAL_DOC_EXCLUDE_DIRS or [])
        max_files = int(Config.LOCAL_DOC_MAX_FILES or 0)
        max_chars = int(Config.LOCAL_DOC_MAX_CHARS or 0)
        total = 0
        added = 0
        for base in (Config.LOCAL_DOC_DIRS or []):
            base = Path(base)
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if p.is_dir():
                    continue
                rel = str(p.relative_to(Config.BASE_DIR)) if str(p).startswith(str(Config.BASE_DIR)) else str(p)
                if any(part in exclude_dirs for part in Path(rel).parts):
                    continue
                suffix = p.suffix.lower()
                if exts and suffix not in exts and suffix not in img_exts:
                    continue
                total += 1
                if max_files and total > max_files:
                    break
                try:
                    doc_id = hashlib.sha256(str(p).encode("utf-8")).hexdigest()[:16]
                    out = clean_dir / f"local_{doc_id}.txt"
                    if out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
                        continue
                    if suffix in img_exts and getattr(Config, "OCR_ENABLED", False):
                        text = ocr_image_file(p)
                        if not text:
                            continue
                    else:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                    if not text:
                        continue
                    if max_chars and len(text) > max_chars:
                        text = text[:max_chars]
                    out.write_text(text, encoding="utf-8")
                    added += 1
                except Exception:
                    continue
            if max_files and total >= max_files:
                break
        if added:
            logger.info(f"[LOCAL] 📚 Local docs ingested to clean: +{added}, scanned={total}")
        _save_local_docs_state(added, total)
        return {"skipped": False, "added": added, "scanned": total}
    except Exception as e:
        logger.warning(f"[LOCAL] ⚠️  Local docs ingest failed: {e}")
        return {"skipped": False, "added": 0, "scanned": 0, "error": str(e)}


def build_vector_store_from_clean() -> dict:
    clean_dir = Config.DATA_DIR / "clean"
    texts = []
    metas = []
    if clean_dir.exists():
        for p in clean_dir.iterdir():
            if p.suffix == ".txt":
                try:
                    texts.append(p.read_text(encoding="utf-8", errors="ignore"))
                    metas.append({"id": p.stem, "meta": {"source": str(p)}})
                except Exception:
                    continue

    vs = VectorStore()
    vs.texts = []
    vs.metadatas = []
    vs.embeddings = None
    vs.faiss_index = None
    vs.tfidf = None
    vs.nn = None
    for i, t in enumerate(texts):
        vs.add(metas[i]["id"], t, metadata=metas[i]["meta"])
    if texts:
        logger.info(f"[LOCAL] 🔨 Building vector store from {len(texts)} documents")
        vs.build()
        vs.save()
        logger.info("[LOCAL] ✅ Vector store built and saved")
    return {"count": len(texts)}
