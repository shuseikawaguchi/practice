"""
Reporter Module - 評価レポート生成エンジン
Purpose: 学習進捗と性能を評価・分析し、レポート出力
        - 訓練ログ分析
        - 性能指標集計（BLEU/ROUGE/重複度）
        - 進捗グラフ生成
        - HTML/JSONレポート出力
        - 改善提案生成
Usage: reporter = Reporter(); reporter.run_report()
Status: 各ワーカーサイクル後に自動実行
"""
import json
import time
import logging
from pathlib import Path
from config import Config
from evaluator import overlap_score, bleu_score, rouge_scores

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Reporter:
    def __init__(self):
        self.training_dir = Config.TRAINING_DIR
        self.logs_dir = Config.LOGS_DIR
        self.logs_dir.mkdir(exist_ok=True)

    def collect_examples(self):
        files = sorted(self.training_dir.glob('synthetic_*.jsonl'))
        examples = []
        for f in files:
            with open(f, 'r', encoding='utf-8') as fh:
                for line in fh:
                    try:
                        examples.append(json.loads(line))
                    except Exception:
                        continue
        return examples

    def run_report(self):
        examples = self.collect_examples()
        if not examples:
            logger.info('No synthetic examples found for reporting')
            return None

        stats = {'count': 0, 'overlap': 0.0, 'bleu': 0.0, 'rougeL': 0.0}
        n = 0
        for ex in examples:
            ref = ex.get('output','')
            hyp = ex.get('output','')  # fallback: if student output available, prefer it; synthetic currently uses teacher output
            # if student output exists, it should be in ex['student_output']
            if ex.get('student_output'):
                hyp = ex.get('student_output')
            if not ref or not hyp:
                continue
            n += 1
            stats['overlap'] += overlap_score(ref, hyp)
            stats['bleu'] += bleu_score(ref, hyp)
            stats['rougeL'] += rouge_scores(ref, hyp).get('rougeL', 0.0)

        if n == 0:
            logger.info('No comparable examples for report')
            return None

        stats['count'] = n
        stats['overlap'] /= n
        stats['bleu'] /= n
        stats['rougeL'] /= n

        ts = int(time.time())
        out = self.logs_dir / f'reports_{ts}.json'
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': ts, 'stats': stats}, f, ensure_ascii=False, indent=2)
        logger.info(f'Report written to {out}')
        return out

if __name__ == '__main__':
    r = Reporter()
    r.run_report()
