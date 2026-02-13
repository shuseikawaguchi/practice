#!/usr/bin/env python3
"""
Screen OCR tool with optional dedup + Ollama summary.

Requires:
- pyautogui
- pytesseract (and local tesseract binary)
- opencv-python
- pillow
- requests
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import difflib
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np
import pyautogui
import pytesseract
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


Region = Optional[Tuple[int, int, int, int]]  # (left, top, width, height)


@dataclass
class AdvancedScreenOCR:
    interval: float = 2.0
    region: Region = None
    lang: str = "jpn"
    threshold: int = 180
    similarity: float = 0.8
    running: bool = False
    thread: Optional[threading.Thread] = None
    pages: List[str] = field(default_factory=list)
    full_lines: List[str] = field(default_factory=list)

    def _capture_text(self) -> str:
        screenshot = pyautogui.screenshot(region=self.region)
        img = np.array(screenshot)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(thresh, lang=self.lang)
        return text.strip()

    def _is_similar(self, text1: str, text2: str) -> bool:
        ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
        return ratio >= self.similarity

    def _merge_lines(self, new_text: str) -> None:
        new_lines = [l.strip() for l in new_text.split("\n") if l.strip()]
        if not new_lines:
            return
        if not self.full_lines:
            self.full_lines.extend(new_lines)
            return
        overlap_index = 0
        for i in range(len(self.full_lines)):
            tail = self.full_lines[i:]
            if tail == new_lines[: len(tail)]:
                overlap_index = len(tail)
        self.full_lines.extend(new_lines[overlap_index:])

    def _loop(self) -> None:
        previous_text = ""
        while self.running:
            current_text = self._capture_text()
            if current_text:
                self.pages.append(current_text)
                if not self._is_similar(previous_text, current_text):
                    self._merge_lines(current_text)
                    previous_text = current_text
            time.sleep(self.interval)

    def start(self) -> None:
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def get_full_text(self) -> str:
        return "\n".join(self.full_lines)

    def clear(self) -> None:
        self.pages = []
        self.full_lines = []


def summarize_with_ollama_stream(text: str, model: str, url: str) -> None:
    payload = {
        "model": model,
        "prompt": f"以下を要約:\n{text}",
        "stream": True,
    }
    with requests.post(url, json=payload, stream=True, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            print(data.get("response", ""), end="", flush=True)
    print()


def learn_from_text(text: str, rebuild: bool = False) -> dict:
    content = (text or "").strip()
    if not content:
        return {"ok": False, "reason": "empty_text"}

    try:
        from config import Config
        from src.utils.local_doc_ingest import build_vector_store_from_clean
    except Exception as e:
        return {"ok": False, "reason": f"import_failed: {e}"}

    try:
        clean_dir = Config.DATA_DIR / "clean"
        clean_dir.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        out = clean_dir / f"screen_{digest}.txt"

        if out.exists():
            return {"ok": True, "saved": False, "clean_file": str(out), "reason": "already_exists"}

        out.write_text(content, encoding="utf-8")
        result = {"ok": True, "saved": True, "clean_file": str(out)}
        if rebuild:
            result["vector_store"] = build_vector_store_from_clean()
        return result
    except Exception as e:
        return {"ok": False, "reason": f"save_failed: {e}"}


def parse_region(raw: Optional[str]) -> Region:
    if not raw:
        return None
    parts = [int(p.strip()) for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("region must be 'left,top,width,height'")
    return parts[0], parts[1], parts[2], parts[3]


def run_once(region: Region, lang: str, threshold: int) -> str:
    screenshot = pyautogui.screenshot(region=region)
    img = np.array(screenshot)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    text = pytesseract.image_to_string(thresh, lang=lang)
    return text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen OCR tool")
    parser.add_argument("--region", help="left,top,width,height", default=None)
    parser.add_argument("--lang", default="jpn", help="tesseract language code")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--threshold", type=int, default=180)
    parser.add_argument("--similarity", type=float, default=0.8)
    parser.add_argument("--once", action="store_true", help="single capture")
    parser.add_argument("--summary", action="store_true", help="summarize via Ollama")
    parser.add_argument("--learn", action="store_true", help="save OCR text to learning corpus")
    parser.add_argument("--learn-rebuild", action="store_true", help="rebuild vector store after learning")
    parser.add_argument("--learn-min-chars", type=int, default=40, help="minimum chars required to learn")
    parser.add_argument("--model", default="qwen2.5", help="Ollama model")
    parser.add_argument("--ollama-url", default="http://localhost:11434/api/generate")
    args = parser.parse_args()

    region = parse_region(args.region)

    if args.once:
        text = run_once(region=region, lang=args.lang, threshold=args.threshold)
        print(text)
        if args.summary and text:
            summarize_with_ollama_stream(text, model=args.model, url=args.ollama_url)
        if args.learn and len(text) >= max(1, int(args.learn_min_chars)):
            learned = learn_from_text(text, rebuild=bool(args.learn_rebuild))
            print(f"[LEARN] {learned}")
        return

    ocr = AdvancedScreenOCR(
        interval=args.interval,
        region=region,
        lang=args.lang,
        threshold=args.threshold,
        similarity=args.similarity,
    )
    ocr.start()
    try:
        while True:
            time.sleep(args.interval)
            text = ocr.get_full_text()
            if text:
                print(text)
                if args.summary:
                    summarize_with_ollama_stream(text, model=args.model, url=args.ollama_url)
                print("=" * 40)
    except KeyboardInterrupt:
        ocr.stop()
        final_text = (ocr.get_full_text() or "").strip()
        if args.learn:
            if len(final_text) >= max(1, int(args.learn_min_chars)):
                learned = learn_from_text(final_text, rebuild=bool(args.learn_rebuild))
                print(f"[LEARN] {learned}")
            else:
                print(f"[LEARN] skipped: text too short ({len(final_text)} chars)")


if __name__ == "__main__":
    main()
