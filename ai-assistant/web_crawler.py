"""
Simple web crawler with robots.txt respect and rate limiting.
Saves raw HTML to data/raw and metadata to data/crawl_metadata.jsonl
"""
import os
import time
import json
import hashlib
import logging
from urllib.parse import urlparse
import urllib.robotparser

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

from config import Config

logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, rate_delay: float = 1.0, user_agent: str = None):
        self.rate_delay = rate_delay
        self.user_agent = user_agent or Config.CRAWLER_USER_AGENT
        self.raw_dir = Config.DATA_DIR / "raw"
        self.raw_dir.mkdir(exist_ok=True)
        self.meta_file = Config.DATA_DIR / "crawl_metadata.jsonl"

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            # If robots.txt cannot be fetched, be conservative and allow with delay
            logger.warning(f"Could not read robots.txt for {parsed.netloc}; proceeding cautiously")
            return True

    def fetch(self, url: str, max_bytes: int = 5_000_000) -> dict:
        """Fetch a URL, save HTML, and return metadata dict"""
        if requests is None:
            raise RuntimeError("requests is required for web crawling. Install dependencies.")

        if not self._allowed(url):
            logger.info(f"Skipping {url} due to robots.txt")
            return {"status": "skipped", "url": url}

        headers = {"User-Agent": self.user_agent}
        try:
            resp = requests.get(url, headers=headers, timeout=15, stream=True)
            resp.raise_for_status()
            content = resp.content[:max_bytes]
            digest = hashlib.sha256(content).hexdigest()[:16]
            parsed = urlparse(url)
            filename = f"{parsed.netloc}_{digest}.html"
            filepath = self.raw_dir / filename
            with open(filepath, 'wb') as f:
                f.write(content)

            meta = {
                "url": url,
                "status": "fetched",
                "http_status": resp.status_code,
                "bytes": len(content),
                "file": str(filepath),
                "timestamp": int(time.time())
            }
            with open(self.meta_file, 'a', encoding='utf-8') as mf:
                mf.write(json.dumps(meta, ensure_ascii=False) + "\n")

            # polite delay
            time.sleep(self.rate_delay)
            return meta
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return {"url": url, "status": "error", "error": str(e)}

    def fetch_list(self, urls):
        results = []
        for u in urls:
            results.append(self.fetch(u))
        return results
