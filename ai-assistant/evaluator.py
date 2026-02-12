"""
Basic evaluator: computes simple overlap metrics between teacher and student outputs.
Provides token-overlap ratio (very rough) as a quality signal.
"""
import re
from collections import Counter
try:
    import sacrebleu
except Exception:
    sacrebleu = None
try:
    from rouge_score import rouge_scorer
except Exception:
    rouge_scorer = None

WORD_RE = re.compile(r"\w+", re.UNICODE)

def tokenize(text: str):
    return WORD_RE.findall(text.lower())

def overlap_score(ref: str, hyp: str) -> float:
    r = tokenize(ref)
    h = tokenize(hyp)
    if not r or not h:
        return 0.0
    cr = Counter(r)
    ch = Counter(h)
    common = sum((cr & ch).values())
    denom = max(len(r), len(h))
    return common / denom

def bleu_score(ref: str, hyp: str) -> float:
    if sacrebleu is None:
        return 0.0
    try:
        # sacrebleu expects list of refs
        return float(sacrebleu.corpus_bleu([hyp], [[ref]]).score) / 100.0
    except Exception:
        return 0.0

def rouge_scores(ref: str, hyp: str) -> dict:
    if rouge_scorer is None:
        return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}
    try:
        scorer = rouge_scorer.RougeScorer(['rouge1','rouge2','rougeL'], use_stemmer=True)
        sc = scorer.score(ref, hyp)
        return {
            'rouge1': sc['rouge1'].fmeasure,
            'rouge2': sc['rouge2'].fmeasure,
            'rougeL': sc['rougeL'].fmeasure
        }
    except Exception:
        return {'rouge1': 0.0, 'rouge2': 0.0, 'rougeL': 0.0}


if __name__ == '__main__':
    ref = 'これはテストです。正しい出力を確認します。'
    hyp = 'これはテストです。出力を確認します。'
    print('overlap', overlap_score(ref, hyp))
    print('bleu', bleu_score(ref, hyp))
    print('rouge', rouge_scores(ref, hyp))