"""
Worker Module - バックグラウンド学習ワーカー
Purpose: 放置モードで定期的に実行される自動学習ワーカー
        - URLリストをインジェスト
        - ベクトルストア構築
        - 合成データセット生成
        - 訓練データ作成
        - 進化と自動パッチ提案
Usage: python3 worker.py
       または idle_mode.py から自動実行（30分毎）
Status: 放置モード稼働中に継続実行
"""
import os
import time
import json
import signal
import logging
import random
import hashlib
import traceback
from datetime import datetime
from urllib.parse import urlparse
import urllib.robotparser
from pathlib import Path

from config import Config
from ingest import ingest
from vector_store import VectorStore
from llm_manager import LLMManager
from patch_validator import PatchValidator
from src.utils.rss_collector import load_sources, collect_from_sources
from src.utils.local_doc_ingest import ingest_local_docs_to_clean
from src.utils.learning_brains import get_brain_tasks
from multi_teacher_llm import MultiTeacherLLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Worker:
    def __init__(self):
        self.watchlist = Config.WATCHLIST_FILE
        self.interval = Config.WORKER_INTERVAL_SECONDS
        self.pid_file = Config.WORKER_PID_FILE
        self.stop_file = Config.STOP_FILE
        self.training_dir = Config.TRAINING_DIR
        self.llm = LLMManager(model_name=Config.TEACHER_MODEL)
        self.multi_teacher = MultiTeacherLLM() if Config.USE_MULTI_TEACHER else None
        self.vs = VectorStore()
        self._running = False
        self.failure_events_file = Config.FAILURE_EVENTS_FILE
        self.failure_lessons_file = Config.FAILURE_LESSONS_FILE

    def _write_pid(self):
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))

    def _remove_pid(self):
        try:
            os.remove(self.pid_file)
        except Exception:
            pass

    def _should_stop(self):
        return self.stop_file.exists()

    def run_once(self):
        # collect URLs from RSS sources (optional)
        self._collect_rss_urls()
        # ingest local documents into clean corpus
        self._ingest_local_docs_to_clean()
        # read watchlist
        urls = []
        if self.watchlist.exists():
            with open(self.watchlist, 'r', encoding='utf-8') as f:
                urls = [l.strip() for l in f.readlines() if l.strip()]
        # auto populate watchlist if empty
        if not urls and Config.AUTO_POPULATE_WATCHLIST:
            seeds = []
            for group in Config.LEARNING_SOURCES.values():
                seeds.extend(group)
            if seeds:
                try:
                    self.watchlist.write_text("\n".join(seeds) + "\n", encoding="utf-8")
                    urls = seeds
                    logger.info(f"[WORKER] 📌 Watchlist auto-populated with {len(seeds)} seed URLs")
                except Exception as e:
                    logger.warning(f"[WORKER] ⚠️  Failed to auto-populate watchlist: {e}")
        # top up watchlist if too small
        if Config.AUTO_POPULATE_WATCHLIST and Config.MIN_WATCHLIST_SIZE:
            urls = self._ensure_watchlist_minimum(urls)
        # prune robots-blocked URLs to avoid wasted cycles
        urls = self._prune_blocked_urls(urls)
        # cap URLs per cycle
        if Config.MAX_URLS_PER_CYCLE and len(urls) > Config.MAX_URLS_PER_CYCLE:
            urls = urls[:Config.MAX_URLS_PER_CYCLE]
        if not urls:
            logger.info('[WORKER] No URLs in watchlist. Skipping this cycle.')
            return

        logger.info(f'[WORKER] Starting cycle - {len(urls)} URLs to process')
        start_time = time.time()

        # ingest
        try:
            logger.info('[WORKER] ▶️  Ingesting URLs from watchlist')
            ingest(urls)
            logger.info('[WORKER] ✅ Ingest completed')
        except Exception as e:
            logger.error(f'[WORKER] ❌ Ingest failed: {e}')
            self._record_failure("ingest", e, {"url_count": len(urls)})

        # load or rebuild vector store
        if Config.REBUILD_VECTOR_STORE_EACH_CYCLE:
            logger.info('[WORKER] 🔁 Rebuilding vector store each cycle')
            self._build_vector_store_from_clean()
        else:
            if self._should_rebuild_vector_store():
                logger.info('[WORKER] 🔁 Rebuilding vector store (changes detected)')
                self._build_vector_store_from_clean()
            else:
                try:
                    logger.info('[WORKER] ▶️  Loading vector store')
                    self.vs.load()
                    logger.info('[WORKER] ✅ Vector store loaded')
                except Exception:
                    logger.info('[WORKER] ℹ️  No existing vector store to load; building from scratch')
                    self._build_vector_store_from_clean()

        # create synthetic dataset via teacher
        examples_created = 0
        try:
            logger.info('[WORKER] ▶️  Creating synthetic training dataset')
            examples_created = self._create_synthetic_dataset()
            logger.info('[WORKER] ✅ Synthetic dataset created')
        except Exception as e:
            logger.error(f'[WORKER] ❌ Dataset creation failed: {e}')
            self._record_failure("dataset_creation", e, {"url_count": len(urls)})

        # trigger trainer (non-blocking)
        if examples_created >= int(Config.MIN_EXAMPLES_FOR_TRAINING or 0):
            try:
                logger.info('[WORKER] ▶️  Triggering trainer')
                from trainer import Trainer
                trainer = Trainer()
                trainer.train_loop_once()
                logger.info('[WORKER] ✅ Training completed')
            except Exception as e:
                logger.warning(f'[WORKER] ⚠️  Trainer not available or failed: {e}')
                self._record_failure("trainer", e, {"examples_created": examples_created})
        else:
            logger.info('[WORKER] ⏭️  Trainer skipped (few examples)')

        # Attempt automated evolution (Evolver checks Config flag internally)
        try:
            if Config.ENABLE_AUTOMATED_EVOLUTION and examples_created >= int(Config.MIN_EXAMPLES_FOR_EVOLUTION or 0):
                logger.info('[WORKER] ▶️  Running evolution')
                from evolver import Evolver
                ev = Evolver()
                ev.run()
                logger.info('[WORKER] ✅ Evolution completed')
            elif Config.ENABLE_AUTOMATED_EVOLUTION:
                logger.info('[WORKER] ⏭️  Evolution skipped (few examples)')
        except Exception as e:
            logger.debug(f'[WORKER] ℹ️  Evolver not available or failed: {e}')
            self._record_failure("evolution", e, {"examples_created": examples_created})
        
        # Generate evaluation report
        try:
            if examples_created >= int(Config.MIN_EXAMPLES_FOR_REPORT or 0):
                logger.info('[WORKER] ▶️  Generating evaluation report')
                from reporter import Reporter
                rep = Reporter()
                rep.run_report()
                logger.info('[WORKER] ✅ Report generated')
            else:
                logger.info('[WORKER] ⏭️  Report skipped (few examples)')
        except Exception as e:
            logger.debug(f'[WORKER] ℹ️  Reporter not available or failed: {e}')
            self._record_failure("report", e, {"examples_created": examples_created})
        
        # Attempt to generate and validate code patches (if evolution generated candidates)
        try:
            if Config.ENABLE_AUTOMATED_EVOLUTION and examples_created >= int(Config.MIN_EXAMPLES_FOR_PATCH or 0):
                logger.info('[WORKER] ▶️  Attempting auto-patch generation')
                self._attempt_auto_patch_generation()
                logger.info('[WORKER] ✅ Patch generation completed')
            elif Config.ENABLE_AUTOMATED_EVOLUTION:
                logger.info('[WORKER] ⏭️  Patch generation skipped (few examples)')
        except Exception as e:
            logger.debug(f'[WORKER] ℹ️  Auto-patch generation not available or failed: {e}')
            self._record_failure("auto_patch", e, {"examples_created": examples_created})
        
        elapsed = time.time() - start_time
        logger.info(f'[WORKER] 🏁 Cycle completed in {elapsed:.1f} seconds')

    def _record_failure(self, stage: str, exc: Exception, extra: dict | None = None):
        try:
            trace = traceback.format_exc()
            if Config.FAILURE_ANALYSIS_MAX_TRACE_CHARS and len(trace) > Config.FAILURE_ANALYSIS_MAX_TRACE_CHARS:
                trace = trace[-Config.FAILURE_ANALYSIS_MAX_TRACE_CHARS:]
            event = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "stage": stage,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": trace,
                "extra": extra or {},
            }
            self.failure_events_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.failure_events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

            if Config.FAILURE_ANALYSIS_ENABLED:
                lesson = self._analyze_failure(event)
                if lesson:
                    with open(self.failure_lessons_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(lesson, ensure_ascii=False) + "\n")
        except Exception as log_err:
            logger.debug(f"[WORKER] ℹ️  Failure logging skipped: {log_err}")

    def _analyze_failure(self, event: dict) -> dict | None:
        try:
            analysis = None
            if Config.FAILURE_ANALYSIS_USE_LLM and self.llm and self.llm.is_available():
                prompt = (
                    "次の障害ログから、原因の推定と改善策を簡潔に箇条書きで出してください。\n"
                    f"stage: {event.get('stage')}\n"
                    f"error_type: {event.get('error_type')}\n"
                    f"error: {event.get('error')}\n"
                    f"traceback: {event.get('traceback')}\n"
                    f"extra: {json.dumps(event.get('extra', {}), ensure_ascii=False)}\n"
                    "出力形式:\n- 原因: ...\n- 改善策: ..."
                )
                analysis = self.llm.generate(prompt, temperature=0.2, max_tokens=220, use_cache=False)
            else:
                analysis = (
                    f"- 原因: {event.get('error_type')} / {event.get('error')}\n"
                    "- 改善策: 例外の発生箇所を特定し、前提条件・入力の検証を追加する"
                )

            return {
                "timestamp": event.get("timestamp"),
                "stage": event.get("stage"),
                "summary": analysis,
                "error_type": event.get("error_type"),
            }
        except Exception as e:
            logger.debug(f"[WORKER] ℹ️  Failure analysis skipped: {e}")
            return None

    def _ensure_watchlist_minimum(self, urls: list[str]) -> list[str]:
        try:
            min_size = int(Config.MIN_WATCHLIST_SIZE or 0)
            if min_size <= 0:
                return urls
            if len(urls) >= min_size:
                return urls
            pool = []
            for group in Config.LEARNING_SOURCES.values():
                pool.extend(group)
            # also include RSS sources as seeds
            pool.extend(getattr(Config, "RSS_SOURCES", []) or [])
            if not pool:
                return urls
            existing = set(urls)
            random.shuffle(pool)
            added = 0
            max_add = int(Config.WATCHLIST_TOPUP_PER_CYCLE or 0)
            for u in pool:
                if u in existing:
                    continue
                urls.append(u)
                existing.add(u)
                added += 1
                if max_add and added >= max_add:
                    break
                if len(urls) >= min_size:
                    break
            if added:
                try:
                    self.watchlist.write_text("\n".join(urls) + "\n", encoding="utf-8")
                except Exception as e:
                    logger.warning(f"[WORKER] ⚠️  Failed to update watchlist: {e}")
                logger.info(f"[WORKER] 🧩 Watchlist topped up: +{added}, total={len(urls)}")
            return urls
        except Exception as e:
            logger.warning(f"[WORKER] ⚠️  Watchlist top-up failed: {e}")
            return urls

    def _collect_rss_urls(self):
        try:
            sources = load_sources()
        except Exception:
            sources = []
        if not sources:
            return
        try:
            existing = []
            if self.watchlist.exists():
                existing = [l.strip() for l in self.watchlist.read_text(encoding='utf-8').splitlines() if l.strip()]
            new_urls = collect_from_sources(sources, max_items=Config.RSS_MAX_ITEMS)
            merged = existing[:]
            added = 0
            for u in new_urls:
                if u not in merged:
                    merged.append(u)
                    added += 1
            if added:
                self.watchlist.write_text("\n".join(merged) + "\n", encoding="utf-8")
                logger.info(f"[WORKER] 🧲 RSSから{added}件追加しました")
        except Exception as e:
            logger.warning(f"[WORKER] ⚠️  RSS収集に失敗しました: {e}")

    def _prune_blocked_urls(self, urls: list[str]) -> list[str]:
        if not Config.PRUNE_BLOCKED_URLS:
            return urls
        if not urls:
            return urls
        cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        allowed: list[str] = []
        blocked: list[str] = []

        def _allowed(url: str) -> bool:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            key = f"{parsed.scheme}://{parsed.netloc}"
            rp = cache.get(key)
            if rp is None:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(f"{key}/robots.txt")
                try:
                    rp.read()
                except Exception:
                    rp = None
                cache[key] = rp
            if rp is None:
                return True
            return rp.can_fetch(Config.CRAWLER_USER_AGENT, url)

        for u in urls:
            if _allowed(u):
                allowed.append(u)
            else:
                blocked.append(u)

        if blocked:
            logger.info(f"[WORKER] 🚫 robots.txt blocked: {len(blocked)}")
            if Config.PRUNE_BLOCKED_URLS_SAVE:
                try:
                    self.watchlist.write_text("\n".join(allowed) + "\n", encoding="utf-8")
                except Exception as e:
                    logger.warning(f"[WORKER] ⚠️  Failed to save pruned watchlist: {e}")
        return allowed

    def _ingest_local_docs_to_clean(self, force: bool = False):
        try:
            return ingest_local_docs_to_clean(force=force)
        except Exception as e:
            logger.warning(f"[WORKER] ⚠️  Local docs ingest failed: {e}")
            return {"error": str(e)}

    def _build_vector_store_from_clean(self):
        clean_dir = Config.DATA_DIR / 'clean'
        texts = []
        metas = []
        if clean_dir.exists():
            for p in clean_dir.iterdir():
                if p.suffix == '.txt':
                    try:
                        texts.append(p.read_text(encoding='utf-8', errors='ignore'))
                        metas.append({'id': p.stem, 'meta': {'source': str(p)}})
                    except Exception:
                        continue
        # reuse existing vector store to avoid repeated model downloads
        self.vs.texts = []
        self.vs.metadatas = []
        self.vs.embeddings = None
        self.vs.faiss_index = None
        self.vs.tfidf = None
        self.vs.nn = None
        for i, t in enumerate(texts):
            self.vs.add(metas[i]['id'], t, metadata=metas[i]['meta'])
        if texts:
            logger.info(f'[WORKER] 🔨 Building vector store from {len(texts)} documents')
            self.vs.build()
            self.vs.save()
            logger.info('[WORKER] ✅ Vector store built and saved')
            self._save_clean_index_state(clean_dir, len(texts))

    def _get_clean_stats(self, clean_dir: Path) -> tuple[int, float]:
        count = 0
        latest = 0.0
        if clean_dir.exists():
            for p in clean_dir.iterdir():
                if p.suffix == '.txt':
                    count += 1
                    try:
                        latest = max(latest, p.stat().st_mtime)
                    except Exception:
                        pass
        return count, latest

    def _load_clean_index_state(self) -> dict:
        try:
            if Config.CLEAN_INDEX_STATE_FILE.exists():
                return json.loads(Config.CLEAN_INDEX_STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
        return {}

    def _save_clean_index_state(self, clean_dir: Path, count: int):
        try:
            _, latest = self._get_clean_stats(clean_dir)
            state = {
                "count": count,
                "latest_mtime": latest,
                "built_at": time.time(),
            }
            Config.CLEAN_INDEX_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass

    def _should_rebuild_vector_store(self) -> bool:
        clean_dir = Config.DATA_DIR / 'clean'
        count, latest = self._get_clean_stats(clean_dir)
        state = self._load_clean_index_state()
        last_count = int(state.get("count") or 0)
        last_latest = float(state.get("latest_mtime") or 0)
        last_built = float(state.get("built_at") or 0)
        min_interval = int(Config.REBUILD_VECTOR_STORE_MIN_INTERVAL_SECONDS or 0)
        # rebuild if never built or index files missing
        if not (Config.MODELS_DIR / 'metadatas.pkl').exists():
            return True
        if count == 0:
            return False
        changed = (count != last_count) or (latest > last_latest + 1e-6)
        if not changed:
            return False
        if min_interval <= 0:
            return True
        return (time.time() - last_built) >= min_interval

    def _create_synthetic_dataset(self) -> int:
        # Query some example prompts from the vector store and ask teacher to generate high-quality outputs
        tasks = get_brain_tasks()
        random.shuffle(tasks)
        if Config.PROMPTS_PER_CYCLE:
            tasks = tasks[:Config.PROMPTS_PER_CYCLE]

        examples = []
        seen = set()
        for i, task in enumerate(tasks, 1):
            q = task["prompt"]
            task_type = task.get("task_type", "general")
            try:
                logger.debug(f'[WORKER] Querying dataset prompt {i}/{len(tasks)}: {q[:50]}...')
                results = self.vs.query(q, k=Config.VS_QUERY_K)
            except Exception:
                results = []
            context = ''
            for r in results:
                chunk = r['text'][:1000]
                context += f"[SOURCE:{r['meta'].get('source','')}]\n{chunk}\n\n"
                if Config.MAX_CONTEXT_CHARS and len(context) >= Config.MAX_CONTEXT_CHARS:
                    context = context[:Config.MAX_CONTEXT_CHARS]
                    break
            if Config.MIN_CONTEXT_CHARS and len(context) < Config.MIN_CONTEXT_CHARS:
                if not Config.ALLOW_EMPTY_CONTEXT:
                    continue
                prompt = (
                    "以下の要求に答えてください。\n\n"
                    f"要求:\n{q}\n\n応答："
                )
            else:
                prompt = (
                    "以下のコンテキストを参照して、要求に答えてください。\n\n"
                    f"コンテキスト:\n{context}\n"
                    f"要求:\n{q}\n\n応答："
                )
            logger.debug(f'[WORKER] Generating response from teacher model')
            response = self._generate_with_brains(prompt, task_type)
            if response:
                if response.startswith('エラー:'):
                    continue
                if self.llm._needs_japanese_retry(response):
                    retry_prompt = (
                        prompt
                        + "\n\n【重要】英語は使わず、日本語だけで簡潔に回答してください。"
                        + "\n【重要】英語の単語・文章を一切含めないでください。"
                    )
                    response = self._generate_with_brains(retry_prompt, task_type)
                    if not response or response.startswith('エラー:'):
                        continue
                if Config.MIN_OUTPUT_CHARS and len(response) < Config.MIN_OUTPUT_CHARS:
                    if not Config.ALLOW_SHORT_OUTPUT:
                        continue
                h = hashlib.sha256(response.encode('utf-8')).hexdigest()
                if h in seen:
                    continue
                seen.add(h)
                examples.append({'input': prompt, 'output': response})
                logger.debug(f'[WORKER] Generated {len(response)} token response')

        # Save dataset
        if examples:
            ts = int(time.time())
            outf = self.training_dir / f'synthetic_{ts}.jsonl'
            with open(outf, 'w', encoding='utf-8') as f:
                for ex in examples:
                    f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            logger.info(f'[WORKER] 📊 Synthetic dataset written: {outf} ({len(examples)} examples)')
        return len(examples)

    def _generate_with_brains(self, prompt: str, task_type: str) -> str:
        if self.multi_teacher:
            try:
                import asyncio
                text, meta = asyncio.run(
                    self.multi_teacher.generate_ensemble(prompt, task_type=task_type, temperature=0.2)
                )
                if text and not text.startswith('エラー:'):
                    return text
            except Exception as e:
                logger.debug(f'[WORKER] ℹ️  Multi-teacher failed: {e}')
        return self.llm.generate(prompt, temperature=0.2, max_tokens=800)

    def _attempt_auto_patch_generation(self):
        """
        Attempt to generate a code patch if the system has learned a new feature.
        This is a placeholder for future auto-edit proposals.
        """
        # Check if there are unapproved patches waiting
        proposed = PatchValidator.list_proposals(status='PROPOSED')
        if proposed:
            logger.info(f'[WORKER] 📋 {len(proposed)} proposed patches awaiting approval')
            for p in proposed:
                title = p.get("title", "(no title)")
                desc = p.get("description", "")
                logger.info(f'[WORKER]   - {title}: {desc[:50]}...')
            return

        candidates = self._get_auto_patch_candidates()
        if not candidates:
            logger.info('[WORKER] ℹ️  No auto-patch candidates available')
            return

        target = random.choice(candidates)
        target_path = (Config.PROJECT_ROOT / target)
        try:
            original = target_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f'[WORKER] ⚠️  Failed to read {target}: {e}')
            return

        if len(original) > 20000:
            logger.info(f'[WORKER] ⏭️  Skip auto-patch for large file: {target}')
            return

        lessons = self._load_recent_failure_lessons(max_lines=8)
        focus = "直近の障害はありません。保守性・堅牢性を少し改善してください。"
        if lessons:
            focus = "直近の障害と学び:\n" + "\n".join(lessons)

        prompt = (
            "次のファイルを小さく改善してください。出力はJSONのみ。\n"
            "制約: 既存の機能を壊さず、変更は最小限。\n"
            "形式: {\"title\":...,\"description\":...,\"files\":{\"path\":\"content\"}}\n"
            f"対象ファイル: {target}\n"
            f"改善方針:\n{focus}\n\n"
            "--- 現在の内容 ---\n"
            f"{original}\n"
        )

        response = self._generate_with_brains(prompt, task_type="code")
        data = self._extract_json(response)
        if not data:
            logger.info('[WORKER] ℹ️  Auto-patch generation returned no JSON')
            self._record_failure("auto_patch_parse", ValueError("no_json"), {"target": target})
            return

        files = data.get("files") or {}
        if not isinstance(files, dict) or not files:
            logger.info('[WORKER] ℹ️  Auto-patch JSON missing files')
            return
        if Config.AUTO_APPLY_MAX_FILES and len(files) > int(Config.AUTO_APPLY_MAX_FILES):
            logger.info('[WORKER] ⏭️  Auto-patch too many files; skipped')
            return

        if target not in files:
            logger.info('[WORKER] ⏭️  Auto-patch did not modify target; skipped')
            return

        new_content = files.get(target)
        if not new_content or new_content.strip() == original.strip():
            logger.info('[WORKER] ⏭️  Auto-patch produced no changes')
            return

        title = data.get("title") or f"Auto-improve {target}"
        description = data.get("description") or "Auto-generated improvement"

        try:
            PatchValidator.create_and_validate(title, description, files, auto_propose=True)
            logger.info('[WORKER] ✅ Auto-patch proposed')
        except Exception as e:
            logger.warning(f'[WORKER] ⚠️  Auto-patch proposal failed: {e}')

    def start(self):
        logger.info('[WORKER] 🚀 Worker daemon starting...')
        self._write_pid()
        logger.info(f'[WORKER] 📝 PID written to {self.pid_file}')
        self._running = True
        try:
            while self._running and not self._should_stop():
                logger.info('[WORKER] ═══════════════════════════════════════════════════════')
                try:
                    self.run_once()
                except Exception as e:
                    logger.error(f'[WORKER] ❌ Error in run_once: {e}', exc_info=True)
                logger.info(f'[WORKER] 💤 Sleeping for {self.interval} seconds until next cycle')
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info('[WORKER] ⚠️  Worker interrupted by user')
        finally:
            self._remove_pid()
            logger.info('[WORKER] 🛑 Worker daemon stopped')

    def _get_auto_patch_candidates(self) -> list[str]:
        preferred = [
            "worker.py",
            "config.py",
            "evolver.py",
            "trainer.py",
            "patch_validator.py",
            "llm_manager.py",
            "api.py",
            "ingest.py",
            "vector_store.py",
        ]
        candidates = []
        for p in preferred:
            if (Config.PROJECT_ROOT / p).exists():
                candidates.append(p)

        exts = set(Config.AUTO_PATCH_CANDIDATE_EXTS or [".py"])
        exclude_dirs = set(Config.AUTO_PATCH_EXCLUDE_DIRS or [])
        max_candidates = int(Config.AUTO_PATCH_MAX_CANDIDATES or 0)

        for p in Config.PROJECT_ROOT.rglob("*"):
            if p.is_dir():
                if p.name in exclude_dirs:
                    continue
                continue
            if p.suffix not in exts:
                continue
            parts = set(p.parts)
            if parts.intersection(exclude_dirs):
                continue
            rel = p.relative_to(Config.PROJECT_ROOT).as_posix()
            if rel not in candidates:
                candidates.append(rel)
            if max_candidates and len(candidates) >= max_candidates:
                break

        return candidates

    def _load_recent_failure_lessons(self, max_lines: int = 5) -> list[str]:
        path = self.failure_lessons_file
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return []
            recent = lines[-max_lines:]
            out = []
            for ln in recent:
                try:
                    obj = json.loads(ln)
                    summary = obj.get("summary") or ""
                    if summary:
                        out.append(summary)
                except Exception:
                    continue
            return out
        except Exception:
            return []

    def _extract_json(self, text: str) -> dict | None:
        if not text:
            return None
        # strip code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1].strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()

        # try direct parse
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        # fallback: scan for first valid JSON object
        start = cleaned.find("{")
        while start != -1:
            end = cleaned.find("}", start)
            while end != -1:
                candidate = cleaned[start:end + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    pass
                end = cleaned.find("}", end + 1)
            start = cleaned.find("{", start + 1)
        return None

if __name__ == '__main__':
    w = Worker()
    w.start()
