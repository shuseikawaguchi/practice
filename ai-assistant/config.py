"""
Configuration Module - System-wide settings and paths
Purpose: 中央集約的な設定管理。全モジュールで使用される定数、パス、設定値を定義
         このファイルを編集すると、システム全体の動作が変わります
Usage: from config import Config
       Config.DATA_DIR, Config.ENABLE_AUTOMATED_EVOLUTION など
"""
from pathlib import Path
import json
import os

class Config:
    # Project paths
    PROJECT_ROOT = Path(__file__).parent
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    MODELS_DIR = BASE_DIR / "models"
    LOGS_DIR = BASE_DIR / "logs"
    FAILURE_REPORTS_DIR = DATA_DIR / "failure_reports"
    FAILURE_EVENTS_FILE = FAILURE_REPORTS_DIR / "failure_events.jsonl"
    FAILURE_LESSONS_FILE = FAILURE_REPORTS_DIR / "failure_lessons.jsonl"
    
    # Create directories if they don't exist
    for dir_path in [DATA_DIR, MODELS_DIR, LOGS_DIR, FAILURE_REPORTS_DIR]:
        dir_path.mkdir(exist_ok=True)
    
    # Model configuration
    TEACHER_MODEL = "llama3.1:8b"  # Ollama modelname
    STUDENT_MODEL_NAME = "student_ai"
    STUDENT_MODEL_PATH = MODELS_DIR / "student_model.pt"
    EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
    
    # Training configuration
    LEARNING_RATE = 5e-5
    BATCH_SIZE = 16
    EPOCHS = 6
    MAX_LENGTH = 1024
    
    # Memory configuration
    MEMORY_FILE = DATA_DIR / "ai_memory.json"
    INTERACTION_LOG = DATA_DIR / "interactions.jsonl"
    
    # Skills configuration
    SKILLS = {
        "code_generation": True,
        "ui_generation": True,
        "model_3d_generation": True,
        "text_generation": True,
    }
    
    # API configuration
    OLLAMA_BASE_URL = "http://localhost:11434"
    API_PORT = int(os.getenv("AI_ASSISTANT_API_PORT", "8000"))
    API_HOST = os.getenv("AI_ASSISTANT_API_HOST", "192.168.1.11")
    API_TOKEN = os.getenv("AI_ASSISTANT_API_TOKEN", "")  # 任意: 外部アクセス時の簡易トークン
    API_ALLOWED_IPS = [ip.strip() for ip in os.getenv("AI_ASSISTANT_ALLOWED_IPS", "").split(",") if ip.strip()]

    # LLM response tuning (speed vs quality)
    LLM_MAX_TOKENS = 640
    LLM_TIMEOUT_SECONDS = 120
    LLM_HISTORY_TURNS = 3
    LLM_CACHE_SIZE = 128
    RAG_CACHE_SIZE = 128
    LLM_CHAT_TEMPERATURE = 0.4
    LLM_CHAT_MAX_TOKENS = 900
    LLM_TOP_P = 0.9
    LLM_REPEAT_PENALTY = 1.12

    # Provider selection / auto-replacement policy
    PROVIDER_SCORES_FILE = DATA_DIR / "provider_scores.json"
    PROVIDER_POLICY = {
        "llm": {
            "preferred": "ollama",
            "min_score": 0.85,
            "auto_switch": True,
        },
        "ocr": {
            "preferred": "tesseract",
            "min_score": 0.85,
            "auto_switch": True,
        },
    }
    INTERNAL_LLM_BASE_URL = os.getenv("AI_ASSISTANT_INTERNAL_LLM_URL", "")

    # Browser automation
    BROWSER_HEADLESS = os.getenv("AI_ASSISTANT_BROWSER_HEADLESS", "1") == "1"
    BROWSER_TIMEOUT_MS = int(os.getenv("AI_ASSISTANT_BROWSER_TIMEOUT_MS", "20000"))
    BROWSER_TEXT_MAX_CHARS = int(os.getenv("AI_ASSISTANT_BROWSER_TEXT_MAX_CHARS", "4000"))
    SCREENSHOT_DIR = DATA_DIR / "screenshots"
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    # Failure analysis / learning
    FAILURE_ANALYSIS_ENABLED = True
    FAILURE_ANALYSIS_USE_LLM = True
    FAILURE_ANALYSIS_MAX_TRACE_CHARS = 4000

    # RSS collector
    RSS_SOURCES = [
        "https://blog.python.org/feeds/posts/default",
        "https://fastapi.tiangolo.com/index.xml",
        "https://developer.mozilla.org/en-US/blog/rss.xml",
        "https://github.blog/feed/",
        "https://engineering.atspotify.com/feed/",
        "https://aws.amazon.com/blogs/machine-learning/feed/",
        "https://openai.com/blog/rss/",
        "https://arxiv.org/rss/cs.AI",
        "https://arxiv.org/rss/cs.LG",
        "https://arxiv.org/rss/cs.CL",
        "https://paperswithcode.com/rss",
        "https://huggingface.co/blog/feed.xml",
        "https://deepmind.google/blog/rss.xml",
        "https://www.anthropic.com/news/rss.xml",
        "https://www.infoq.com/feed/",
        "https://www.atmarkit.co.jp/rss/rss.xml",
        "https://www.publickey1.jp/atom.xml",
    ]
    RSS_MAX_ITEMS = 200
    RSS_TIMEOUT_SECONDS = 10

    # Learning brains
    USE_MULTI_TEACHER = False

    # Code search
    SEARCH_MAX_FILES = 200
    SEARCH_MAX_MATCHES = 50
    # Worker / ingest configuration
    CRAWLER_USER_AGENT = "ai-assistant-crawler/1.0"
    PRUNE_BLOCKED_URLS = True
    PRUNE_BLOCKED_URLS_SAVE = True
    WATCHLIST_FILE = DATA_DIR / "watchlist.txt"
    WORKER_INTERVAL_SECONDS = 60 * 2  # default 2 minutes
    WORKER_PID_FILE = DATA_DIR / "worker.pid"
    STOP_FILE = DATA_DIR / "STOP"
    TRAINING_DIR = DATA_DIR / "training"
    AUTO_POPULATE_WATCHLIST = True
    MIN_WATCHLIST_SIZE = 800
    WATCHLIST_TOPUP_PER_CYCLE = 300
    REBUILD_VECTOR_STORE_EACH_CYCLE = False
    REBUILD_VECTOR_STORE_MIN_INTERVAL_SECONDS = 1800
    CLEAN_INDEX_STATE_FILE = DATA_DIR / "clean_index_state.json"
    LOCAL_DOC_DIRS = [
        BASE_DIR,
        BASE_DIR / "docs",
        BASE_DIR / "data",
    ]
    LOCAL_DOC_EXTS = [
        ".md", ".txt", ".json", ".yaml", ".yml", ".rst", ".csv",
        ".py", ".js", ".ts", ".html", ".css",
    ]
    # OCR ingest for screenshots / images
    OCR_ENABLED = True
    OCR_IMAGE_EXTS = [
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif",
    ]
    OCR_LANG = os.getenv("AI_ASSISTANT_OCR_LANG", "jpn+eng")
    OCR_MAX_PIXELS = 12_000_000  # downscale if larger than ~12MP
    OCR_TESS_CONFIG = os.getenv("AI_ASSISTANT_OCR_TESS_CONFIG", "--oem 1 --psm 6")
    OCR_UPSCALE_MIN_WIDTH = 900
    OCR_WATCH_ENABLED = os.getenv("AI_ASSISTANT_OCR_WATCH_ENABLED", "1") == "1"
    OCR_WATCH_INTERVAL_SECONDS = int(os.getenv("AI_ASSISTANT_OCR_WATCH_INTERVAL_SECONDS", "60"))
    OCR_WATCH_CAPTURE_SCREEN = os.getenv("AI_ASSISTANT_OCR_WATCH_CAPTURE_SCREEN", "1") == "1"
    # capture backend: auto|mss|pyautogui|adb
    OCR_WATCH_CAPTURE_BACKEND = os.getenv("AI_ASSISTANT_OCR_WATCH_CAPTURE_BACKEND", "auto")
    # adb device id for adb backend (optional)
    OCR_WATCH_ADB_DEVICE = os.getenv("AI_ASSISTANT_OCR_WATCH_ADB_DEVICE", "")
    # target fps for live capture when using continuous capture (affects interval)
    OCR_WATCH_CAPTURE_FPS = float(os.getenv("AI_ASSISTANT_OCR_WATCH_CAPTURE_FPS", "1.0"))
    OCR_WATCH_DIRS = [
        DATA_DIR / "screenshots",
        DATA_DIR / "uploads",
    ]
    OCR_WATCH_STATE_FILE = DATA_DIR / "ocr_watch_state.json"
    # persistent config for OCR watch (auto-start)
    OCR_WATCH_CONFIG_FILE = DATA_DIR / "ocr_watch_config.json"
    LOCAL_DOC_MAX_FILES = 10000
    LOCAL_DOC_MAX_CHARS = 120000
    LOCAL_DOC_INGEST_MIN_INTERVAL_SECONDS = 1800
    LOCAL_DOC_INGEST_STATE_FILE = DATA_DIR / "local_docs_state.json"
    LOCAL_DOC_EXCLUDE_DIRS = [
        ".git",
        ".venv",
        "__pycache__",
        "models",
        "backups",
        "auto_edits",
        "logs",
        "data/patches",
    ]
    MAX_URLS_PER_CYCLE = 400
    PROMPTS_PER_CYCLE = 240
    MIN_OUTPUT_CHARS = 60
    MIN_CONTEXT_CHARS = 80
    MAX_CONTEXT_CHARS = 4000
    VS_QUERY_K = 6
    ALLOW_EMPTY_CONTEXT = True
    ALLOW_SHORT_OUTPUT = True
    MIN_EXAMPLES_FOR_TRAINING = 20
    MIN_EXAMPLES_FOR_EVOLUTION = 80
    MIN_EXAMPLES_FOR_REPORT = 20
    MIN_EXAMPLES_FOR_PATCH = 80
    LEARNING_SOURCES = {
        "japanese": [
            "https://ja.wikipedia.org/wiki/日本語",
            "https://ja.wikipedia.org/wiki/敬語",
            "https://ja.wikipedia.org/wiki/文法",
            "https://ja.wikipedia.org/wiki/漢字",
        ],
        "ai": [
            "https://arxiv.org/list/cs.AI/recent",
            "https://arxiv.org/list/cs.LG/recent",
            "https://arxiv.org/list/cs.CL/recent",
            "https://paperswithcode.com/",
            "https://huggingface.co/blog",
            "https://openai.com/blog/",
            "https://deepmind.google/discover/blog/",
            "https://www.anthropic.com/news",
        ],
        "tech": [
            "https://developer.mozilla.org/ja/",
            "https://docs.python.org/ja/3/",
            "https://fastapi.tiangolo.com/",
        ],
        "entertainment": [
            "https://ja.wikipedia.org/wiki/ゲーム",
            "https://ja.wikipedia.org/wiki/アニメ",
            "https://ja.wikipedia.org/wiki/映画",
            "https://ja.wikipedia.org/wiki/音楽",
        ],
    }

    # Create training dir
    TRAINING_DIR.mkdir(exist_ok=True)
    # Automated evolution settings (default: enabled)
    ENABLE_AUTOMATED_EVOLUTION = True
    EVOLUTION_MAX_TRIALS = 4
    EVOLUTION_VALIDATION_SIZE = 20
    BACKUP_DIR = BASE_DIR / "backups"
    BACKUP_DIR.mkdir(exist_ok=True)
    # Exclude repository code files from ingestion
    EXCLUDE_PATTERNS = ["*.py", "*.md", "scripts/*"]

    # Auto-edit settings
    AUTO_EDIT_DIR = BASE_DIR / "auto_edits"
    AUTO_EDIT_DIR.mkdir(exist_ok=True)
    AUTO_EDIT_BRANCH_PREFIX = "auto/edit"
    AUTO_EDIT_COMMIT_MESSAGE_TEMPLATE = "Auto-edit: proposed changes by assistant"
    # Auto-apply settings (higher freedom with guardrails)
    AUTO_APPROVE_PATCHES = True
    AUTO_APPLY_PATCHES = True
    AUTO_APPLY_REQUIRE_VALIDATION = True
    AUTO_APPLY_MAX_FILES = 20
    AUTO_APPLY_ALLOWED_PATHS = [
        "",  # allow any project path except denied dirs
    ]
    AUTO_APPLY_DENY_DIRS = [
        ".git/",
        ".venv/",
        "data/",
        "models/",
        "logs/",
        "backups/",
        "auto_edits/",
    ]
    AUTO_APPLY_POSTCHECK_ENABLED = True
    AUTO_APPLY_POSTCHECK_TIMEOUT = 60
    AUTO_APPLY_POSTCHECK_COMMANDS = []
    AUTO_PATCH_CANDIDATE_EXTS = [".py"]
    AUTO_PATCH_MAX_CANDIDATES = 300
    AUTO_PATCH_EXCLUDE_DIRS = [
        ".git",
        ".venv",
        "data",
        "models",
        "logs",
        "backups",
        "auto_edits",
        "__pycache__",
    ]
    # Automatic file placement map: component -> directory relative to PROJECT_ROOT
    AUTO_FILE_MAP = {
        "core": BASE_DIR / "src" / "core",
        "modules": BASE_DIR / "src" / "modules",
        "monitoring": BASE_DIR / "src" / "monitoring",
        "generation": BASE_DIR / "src" / "generation",
        "perfection": BASE_DIR / "src" / "perfection",
        "utils": BASE_DIR / "src" / "utils",
        "docs": BASE_DIR / "docs",
        "data": DATA_DIR,
        "patches": DATA_DIR / "patches",
    }
    # Ensure mapped directories exist
    for _p in AUTO_FILE_MAP.values():
        _p.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_auto_path(component: str, filename: str = None):
        """Return a Path for a component and optional filename using AUTO_FILE_MAP."""
        base = Config.AUTO_FILE_MAP.get(component, Config.BASE_DIR)
        return base / filename if filename else base

# Initialize memory file if it doesn't exist
if not Config.MEMORY_FILE.exists():
    Config.MEMORY_FILE.write_text(json.dumps({"conversations": [], "learned_skills": []}, indent=2))
