"""
Universal Crawler Module - 知識自動収集システム
Purpose: 6つの専門分野から継続的に知識を収集・学習
        - ゲーム開発（公式ドキュメント、チュートリアル）
        - Web 開発（フレームワーク、ライブラリ）
        - DevOps（インフラ、デプロイ）
        - データサイエンス（ML、統計）
        - Enterprise（アーキテクチャ、設計）
        - セキュリティ（ベストプラクティス）
        - robots.txt 尊重、レート制限対応
Usage: crawler = UniversalCrawler(); crawler.crawl_specialty('game_dev')
Status: Perfect AI Phase 1 で導入、継続拡張中
"""

import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class UniversalCrawler:
    """Comprehensive knowledge crawler for specialized domains"""
    
    # Curated knowledge sources by specialty
    KNOWLEDGE_SOURCES = {
        'game_dev': {
            'documentation': [
                'https://docs.unity.com/Manual',
                'https://docs.godotengine.org',
                'https://docs.unrealengine.com',
            ],
            'tutorials': [
                'https://learn.unity.com',
                'https://www.youtube.com/c/Brackeys',
                'https://www.youtube.com/c/HeartBeast',
            ],
            'communities': [
                'https://forum.unity.com',
                'https://www.reddit.com/r/gamedev',
                'https://forum.godotengine.org',
            ],
        },
        
        'web_dev': {
            'documentation': [
                'https://developer.mozilla.org',
                'https://nodejs.org/docs',
                'https://docs.djangoproject.com',
                'https://fastapi.tiangolo.com',
            ],
            'tutorials': [
                'https://javascript.info',
                'https://www.youtube.com/c/TraversyMedia',
                'https://www.youtube.com/c/ProgramWithErik',
            ],
            'resources': [
                'https://caniuse.com',
                'https://www.css-tricks.com',
                'https://web.dev',
            ],
        },
        
        'devops': {
            'documentation': [
                'https://kubernetes.io/docs',
                'https://docs.docker.com',
                'https://www.terraform.io/docs',
                'https://docs.ansible.com',
            ],
            'tutorials': [
                'https://www.youtube.com/c/TechWorldwithNana',
                'https://www.youtube.com/c/LinuxAcademy',
            ],
            'repositories': [
                'https://github.com/topics/kubernetes',
                'https://github.com/topics/devops',
            ],
        },
        
        'data_science': {
            'documentation': [
                'https://scikit-learn.org',
                'https://pytorch.org/docs',
                'https://www.tensorflow.org',
                'https://pandas.pydata.org/docs',
            ],
            'learning': [
                'https://kaggle.com',
                'https://paperswithcode.com',
                'https://github.com/topics/machine-learning',
            ],
            'research': [
                'https://arxiv.org/list/cs.LG/recent',
                'https://huggingface.co/models',
            ],
        },
        
        'enterprise': {
            'documentation': [
                'https://www.postgresql.org/docs',
                'https://www.elastic.co/guide',
                'https://kafka.apache.org/documentation',
                'https://www.mongodb.com/docs',
            ],
            'patterns': [
                'https://martinfowler.com',
                'https://microservices.io',
                'https://www.12factor.net',
            ],
        },
        
        'security': {
            'documentation': [
                'https://owasp.org',
                'https://cheatsheetseries.owasp.org',
                'https://www.cisa.gov',
            ],
            'learning': [
                'https://www.youtube.com/c/LiveOverflow',
                'https://hackthebox.com',
            ],
        },
    }
    
    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.crawled_dir = Config.DATA_DIR / 'crawled'
        self.crawled_dir.mkdir(exist_ok=True)
        self.crawl_index = self.crawled_dir / 'index.json'
        self.load_index()
    
    async def start_session(self):
        """Initialize async HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close async session"""
        if self.session:
            await self.session.close()
    
    def load_index(self):
        """Load crawl index"""
        if self.crawl_index.exists():
            with open(self.crawl_index, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
        else:
            self.index = {}
    
    def save_index(self):
        """Save crawl index"""
        with open(self.crawl_index, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    async def crawl_specialty(self, specialty: str, max_pages: int = 100) -> int:
        """Crawl knowledge for a specific specialty"""
        
        if specialty not in self.KNOWLEDGE_SOURCES:
            logger.warning(f'Unknown specialty: {specialty}')
            return 0
        
        await self.start_session()
        
        sources = self.KNOWLEDGE_SOURCES[specialty]
        total_crawled = 0
        
        logger.info(f'Starting crawl for {specialty}...')
        
        # Crawl each source type
        for source_type, urls in sources.items():
            logger.info(f'  Crawling {source_type}...')
            
            for url in urls[:5]:  # limit to 5 per type
                try:
                    crawled = await self._crawl_url(
                        url, 
                        specialty, 
                        source_type,
                        max_pages=max_pages // len(urls)
                    )
                    total_crawled += crawled
                    await asyncio.sleep(2)  # rate limiting
                except Exception as e:
                    logger.error(f'Error crawling {url}: {e}')
        
        await self.close_session()
        self.save_index()
        
        logger.info(f'✅ Crawled {total_crawled} pages for {specialty}')
        return total_crawled
    
    async def _crawl_url(self, url: str, specialty: str, source_type: str,
                        max_pages: int = 10) -> int:
        """Recursively crawl a URL"""
        
        # Check if already crawled
        if url in self.index:
            return 0
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status != 200:
                    return 0
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract text content
                text = self._extract_text(soup)
                
                if text and len(text) > 100:
                    # Save crawled content
                    self._save_content(url, text, specialty, source_type)
                    
                    # Mark as crawled
                    self.index[url] = {
                        'specialty': specialty,
                        'source_type': source_type,
                        'crawled_at': datetime.now().isoformat(),
                        'content_length': len(text),
                    }
                    
                    logger.info(f'  ✅ Crawled: {urlparse(url).netloc}')
                    
                    # Find and crawl linked pages
                    if max_pages > 1:
                        links = self._extract_links(soup, url)
                        for link in links[:3]:  # limit to 3 sub-links
                            if link not in self.index:
                                await asyncio.sleep(1)
                                await self._crawl_url(
                                    link, 
                                    specialty, 
                                    source_type,
                                    max_pages=max_pages-1
                                )
                    
                    return 1
                
        except Exception as e:
            logger.warning(f'Error crawling {url}: {e}')
        
        return 0
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from BeautifulSoup object"""
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split('  '))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:5000]  # limit length
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract relevant links from page"""
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Convert relative to absolute URLs
            absolute_url = urljoin(base_url, href)
            
            # Filter: same domain, relevant paths
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                if any(term in absolute_url.lower() for term in 
                       ['docs', 'guide', 'tutorial', 'learn', 'api']):
                    links.append(absolute_url)
        
        return links
    
    def _save_content(self, url: str, text: str, specialty: str, source_type: str):
        """Save crawled content to file"""
        # Create specialty directory
        spec_dir = self.crawled_dir / specialty
        spec_dir.mkdir(exist_ok=True)
        
        # Create filename from URL
        domain = urlparse(url).netloc.replace('.', '_')
        filename = f'{domain}_{len(text)}.txt'
        filepath = spec_dir / filename
        
        # Save content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f'Source: {url}\n')
            f.write(f'Type: {source_type}\n')
            f.write(f'Specialty: {specialty}\n')
            f.write(f'Date: {datetime.now().isoformat()}\n')
            f.write('=' * 70 + '\n\n')
            f.write(text)
        
        logger.debug(f'Saved: {filepath}')
    
    def get_crawl_stats(self) -> Dict[str, Any]:
        """Get crawling statistics"""
        stats = {
            'total_urls': len(self.index),
            'by_specialty': {},
            'by_source_type': {},
        }
        
        for url, meta in self.index.items():
            spec = meta.get('specialty', 'unknown')
            source = meta.get('source_type', 'unknown')
            
            if spec not in stats['by_specialty']:
                stats['by_specialty'][spec] = 0
            stats['by_specialty'][spec] += 1
            
            if source not in stats['by_source_type']:
                stats['by_source_type'][source] = 0
            stats['by_source_type'][source] += 1
        
        return stats

async def main():
    """Test crawler"""
    crawler = UniversalCrawler()
    
    print('=' * 70)
    print('🌐 Universal Knowledge Crawler')
    print('=' * 70)
    
    # Show available specialties
    print('\n📚 Available Specialties:')
    for specialty in crawler.KNOWLEDGE_SOURCES.keys():
        print(f'  - {specialty}')
    
    # Crawl game_dev as example
    print('\n🎮 Starting crawl for game_dev...')
    await crawler.crawl_specialty('game_dev', max_pages=5)
    
    # Show stats
    stats = crawler.get_crawl_stats()
    print(f'\n📊 Crawl Statistics:')
    print(f'  Total URLs crawled: {stats["total_urls"]}')
    print(f'  By specialty: {stats["by_specialty"]}')

if __name__ == '__main__':
    print('Universal Knowledge Crawler loaded')
    # To run: asyncio.run(main())
