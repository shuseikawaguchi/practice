"""
Ingest Module - データ取得・抽出モジュール
Purpose: URLからコンテンツを取得し、テキスト抽出してベクトルストアに追加
        - Web ページ取得
        - テキスト抽出
        - PDF処理（対応時）
        - コンテンツクリーニング
        - メタデータ保存
Usage: ingest(urls) - URLリストをインジェスト
Status: ワーカーから自動呼び出し、スケジュール定期実行
"""
import sys
import logging
from pathlib import Path

from web_crawler import WebCrawler
from extractor import Extractor
from vector_store import VectorStore
from pii_filter import detect_pii, sanitize
from copyright_filter import check_copyright_in_file
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ingest(urls):
    crawler = WebCrawler(rate_delay=1.0)
    extractor = Extractor()
    store = VectorStore()

    # fetch
    metas = []
    for u in urls:
        meta = crawler.fetch(u)
        metas.append(meta)

    # collect files fetched
    fetched_files = [m.get('file') for m in metas if m.get('status') == 'fetched']

    # extract
    extracted = extractor.extract_many(fetched_files)

    # add to vector store
    for ext in extracted:
        text_file = ext['text_file']
        text = Path(text_file).read_text(encoding='utf-8')
        doc_id = Path(text_file).stem
        # PII detection and sanitization
        try:
            meta = {'source': ext['source_file'], 'title': ext.get('title')}
            # copyright/license check on original HTML if available
            try:
                cinfo = check_copyright_in_file(ext['source_file'])
                meta.update({'copyright': cinfo.get('copyright', False), 'license': cinfo.get('license')})
            except Exception:
                pass

            if detect_pii(text):
                # sanitize and still ingest (avoid storing raw PII)
                clean = sanitize(text)
                meta['pii_sanitized'] = True
                store.add(doc_id, clean, metadata=meta)
            else:
                store.add(doc_id, text, metadata=meta)
        except Exception:
            # fallback: add raw text but mark as unverified
            store.add(doc_id, text, metadata={'source': ext['source_file'], 'title': ext.get('title'), 'pii_detection_error': True})

    # build index
    store.build()
    store.save()
    logger.info('Ingest complete')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python ingest.py urls.txt')
        sys.exit(1)
    urls_file = Path(sys.argv[1])
    urls = [l.strip() for l in urls_file.read_text(encoding='utf-8').splitlines() if l.strip()]
    ingest(urls)
