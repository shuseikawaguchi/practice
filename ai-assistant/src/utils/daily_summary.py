from pathlib import Path
from datetime import datetime, timedelta, date
import json
import os

from config import Config


def _day_range(target_date: date):
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def generate_summary_for_date(target_date: date = None) -> Path:
    """Generate daily learning summary for target_date (defaults to today).

    Writes JSON to data/summaries/YYYY-MM-DD.json and returns the path.
    """
    if target_date is None:
        target_date = date.today()

    start_ts, end_ts = _day_range(target_date)

    cfg = Config
    training_dir = cfg.TRAINING_DIR
    vs_dir = cfg.DATA_DIR / 'vector_store'
    patches_dir = cfg.DATA_DIR / 'patches'

    summary = {
        'date': target_date.isoformat(),
        'new_datasets': 0,
        'new_examples': 0,
        'new_indexed_documents': 0,
        'index_size_mb': 0.0,
        'approved_patches': 0,
        'learned_skills': [],
    }

    # Count synthetic dataset files added today and examples
    if training_dir.exists():
        for f in training_dir.glob('synthetic_*.jsonl'):
            try:
                mtime = f.stat().st_mtime
                if start_ts <= mtime < end_ts:
                    summary['new_datasets'] += 1
                    # count lines as examples
                    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                        summary['new_examples'] += sum(1 for _ in fh)
            except Exception:
                pass

    # Vector store: detect if documents.json was updated today
    if vs_dir.exists():
        docs_file = vs_dir / 'documents.json'
        if docs_file.exists():
            try:
                mtime = docs_file.stat().st_mtime
                if start_ts <= mtime < end_ts:
                    with open(docs_file, 'r', encoding='utf-8') as df:
                        docs = json.load(df)
                        summary['new_indexed_documents'] = len(docs)
                # index size
                idx_file = vs_dir / 'index.faiss'
                if idx_file.exists():
                    summary['index_size_mb'] = round(idx_file.stat().st_size / (1024 * 1024), 2)
            except Exception:
                pass

    # Patches: approved today
    if patches_dir.exists():
        for patch_dir in patches_dir.iterdir():
            if patch_dir.is_dir():
                prop = patch_dir / 'proposal.json'
                if prop.exists():
                    try:
                        with open(prop, 'r', encoding='utf-8') as pf:
                            data = json.load(pf)
                            status = data.get('status', '')
                            # use file mtime as heuristic
                            mtime = prop.stat().st_mtime
                            if status == 'APPROVED' and start_ts <= mtime < end_ts:
                                summary['approved_patches'] += 1
                    except Exception:
                        pass

        # Learned skills: inspect memory file for learned_skills with timestamps
        mem_file = cfg.MEMORY_FILE
        learned = []
        try:
            if mem_file.exists():
                with open(mem_file, 'r', encoding='utf-8') as mf:
                    mem = json.load(mf)
                    skills = mem.get('learned_skills', []) if isinstance(mem, dict) else []
                    for s in skills:
                        # support multiple timestamp keys
                        ts = None
                        for k in ('learned_at', 'added_at', 'timestamp', 'time'):
                            if isinstance(s, dict) and k in s:
                                try:
                                    ts = float(s.get(k))
                                    break
                                except Exception:
                                    pass
                        # if skill is dict with no timestamp, skip date filtering
                        if ts:
                            if start_ts <= ts < end_ts:
                                learned.append(s)
                        else:
                            # no timestamp: include for manual review
                            learned.append(s)
        except Exception:
            pass

        # Normalize learned skills list to names (limit 10)
        learned_names = []
        for item in learned:
            if isinstance(item, dict):
                name = item.get('name') or item.get('skill') or item.get('id')
                if not name:
                    # fallback to stringified dict
                    name = json.dumps(item, ensure_ascii=False)
            else:
                name = str(item)
            learned_names.append(name)

        summary['learned_skills'] = learned_names[:20]
        summary['learned_skills_count'] = len(learned_names)

    # Ensure summaries dir
    summaries_dir = cfg.DATA_DIR / 'summaries'
    summaries_dir.mkdir(parents=True, exist_ok=True)

    out_file = summaries_dir / f'{target_date.isoformat()}.json'
    try:
        out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception:
        # attempt via open
        with open(out_file, 'w', encoding='utf-8') as of:
            json.dump(summary, of, ensure_ascii=False, indent=2)

    return out_file


def load_recent_summaries(days: int = 7):
    cfg = Config
    summaries_dir = cfg.DATA_DIR / 'summaries'
    if not summaries_dir.exists():
        return []

    files = sorted(summaries_dir.glob('*.json'), reverse=True)
    result = []
    for f in files[:days]:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                result.append(data)
        except Exception:
            pass

    return result
