"""
Browser controller using Playwright (sync API).
"""
import base64
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class BrowserInfo:
    url: str
    title: str


class BrowserController:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    def _ensure_started(self, headless: Optional[bool] = None):
        if self._browser and self._page:
            return
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError("Playwright is not installed") from e
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=Config.BROWSER_HEADLESS if headless is None else headless
        )
        self._page = self._browser.new_page()

    def stop(self):
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._playwright = None

    def open(self, url: str, wait_ms: int = 1000, headless: Optional[bool] = None) -> BrowserInfo:
        self._ensure_started(headless=headless)
        if not self._page:
            raise RuntimeError("Browser not initialized")
        self._page.goto(url, wait_until="domcontentloaded", timeout=Config.BROWSER_TIMEOUT_MS)
        if wait_ms:
            self._page.wait_for_timeout(int(wait_ms))
        return BrowserInfo(url=self._page.url, title=self._page.title() or "")

    def click(self, selector: str):
        self._ensure_started()
        if not self._page:
            raise RuntimeError("Browser not initialized")
        self._page.click(selector, timeout=Config.BROWSER_TIMEOUT_MS)

    def type_text(self, selector: str, text: str, press_enter: bool = False):
        self._ensure_started()
        if not self._page:
            raise RuntimeError("Browser not initialized")
        self._page.fill(selector, text)
        if press_enter:
            self._page.keyboard.press("Enter")

    def wait(self, ms: int):
        self._ensure_started()
        if not self._page:
            raise RuntimeError("Browser not initialized")
        self._page.wait_for_timeout(int(ms))

    def get_text(self) -> str:
        self._ensure_started()
        if not self._page:
            raise RuntimeError("Browser not initialized")
        try:
            text = self._page.evaluate("document.body ? document.body.innerText : ''")
        except Exception:
            text = ""
        if not text:
            return ""
        max_chars = int(Config.BROWSER_TEXT_MAX_CHARS or 0)
        if max_chars and len(text) > max_chars:
            return text[:max_chars]
        return text

    def screenshot(self, full_page: bool = False) -> Path:
        self._ensure_started()
        if not self._page:
            raise RuntimeError("Browser not initialized")
        ts = int(time.time())
        out = Config.SCREENSHOT_DIR / f"shot_{ts}.png"
        self._page.screenshot(path=str(out), full_page=bool(full_page))
        return out


def is_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
