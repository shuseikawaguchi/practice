"""
Content extractor: HTML -> cleaned text using readability or BeautifulSoup fallback.
Saves cleaned text to data/clean and returns metadata.
"""
import os
import json
import logging
import warnings
from pathlib import Path

try:
    from readability import Document
except Exception:
    Document = None

try:
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
except Exception:
    BeautifulSoup = None

from config import Config

logger = logging.getLogger(__name__)

class Extractor:
    def __init__(self):
        self.clean_dir = Config.DATA_DIR / "clean"
        self.clean_dir.mkdir(exist_ok=True)

    def extract_from_file(self, html_path: str) -> dict:
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(html_path)

        html = html_path.read_text(encoding='utf-8', errors='ignore')

        text = None
        title = None
        try:
            if Document is not None:
                doc = Document(html)
                title = doc.short_title()
                content = doc.summary()
                # strip tags
                if BeautifulSoup is not None:
                    soup = BeautifulSoup(content, self._detect_bs4_features(content))
                    text = soup.get_text(separator='\n').strip()
                else:
                    # naive fallback
                    text = content
            else:
                if BeautifulSoup is None:
                    raise RuntimeError('BeautifulSoup or readability required for extraction')
                soup = BeautifulSoup(html, self._detect_bs4_features(html))
                # try article tag
                article = soup.find('article')
                if article:
                    text = article.get_text(separator='\n').strip()
                else:
                    # fallback to body text
                    body = soup.find('body')
                    text = body.get_text(separator='\n').strip() if body else soup.get_text(separator='\n').strip()
                title_tag = soup.find('title')
                title = title_tag.get_text().strip() if title_tag else None
        except Exception as e:
            logger.error(f"Extraction error for {html_path}: {e}")
            raise

        # Save cleaned text
        fid = html_path.stem
        out_file = self.clean_dir / f"{fid}.txt"
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text)

        meta = {
            "source_file": str(html_path),
            "text_file": str(out_file),
            "title": title
        }
        return meta

    def _detect_bs4_features(self, text: str) -> str:
        sample = (text or "").lstrip()[:200].lower()
        if sample.startswith("<?xml") or "<rss" in sample or "<feed" in sample:
            return "xml"
        if XMLParsedAsHTMLWarning is not None:
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        return "html.parser"

    def extract_many(self, file_paths):
        results = []
        for p in file_paths:
            try:
                results.append(self.extract_from_file(p))
            except Exception as e:
                logger.error(f"Failed to extract {p}: {e}")
        return results
