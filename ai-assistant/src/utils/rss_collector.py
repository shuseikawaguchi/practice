"""
RSS/Atom collector - 学習用の情報源からURLを収集
"""
import json
import logging
from typing import List
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET
from config import Config

logger = logging.getLogger(__name__)

SOURCES_FILE = Config.DATA_DIR / "rss_sources.json"


def load_sources() -> List[str]:
    if SOURCES_FILE.exists():
        try:
            data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data if x]
        except Exception:
            pass
    return list(Config.RSS_SOURCES)


def save_sources(sources: List[str]):
    try:
        SOURCES_FILE.write_text(json.dumps(sorted(set(sources)), ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save RSS sources: {e}")


def add_source(url: str) -> List[str]:
    sources = load_sources()
    if url and url not in sources:
        sources.append(url)
        save_sources(sources)
    return sources


def remove_source(url: str) -> List[str]:
    sources = [s for s in load_sources() if s != url]
    save_sources(sources)
    return sources


def _fetch_xml(url: str) -> str:
    req = Request(url, headers={"User-Agent": "AI-Assistant/1.0"})
    with urlopen(req, timeout=Config.RSS_TIMEOUT_SECONDS) as res:
        return res.read().decode("utf-8", errors="ignore")


def _parse_links(xml_text: str) -> List[str]:
    links: List[str] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return links

    # RSS 2.0
    for item in root.findall(".//item"):
        link = item.findtext("link")
        if link:
            links.append(link.strip())

    # Atom
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
            href = link.attrib.get("href")
            if href:
                links.append(href.strip())

    # Fallback: any <link> text
    if not links:
        for link in root.findall(".//link"):
            if link.text:
                links.append(link.text.strip())

    # Deduplicate
    dedup = []
    seen = set()
    for l in links:
        if l and l not in seen:
            seen.add(l)
            dedup.append(l)
    return dedup


def collect_from_sources(sources: List[str], max_items: int = 0) -> List[str]:
    urls: List[str] = []
    for src in sources:
        try:
            xml_text = _fetch_xml(src)
            urls.extend(_parse_links(xml_text))
        except Exception as e:
            logger.warning(f"RSS fetch failed: {src} ({e})")
            continue
    if max_items and len(urls) > max_items:
        urls = urls[:max_items]
    return urls
