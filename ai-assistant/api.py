"""
Simple FastAPI wrapper exposing a /api/query endpoint for RAG queries.
"""
from fastapi import FastAPI, Header, HTTPException, Request, UploadFile, File, Form
import threading
import time
import shutil
from pathlib import Path
import os
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from main import AIAssistant
from patch_validator import PatchValidator
from idle_mode import IdleMode
from src.utils.daily_summary import load_recent_summaries
from src.utils.feature_proposals import list_proposals as list_feature_proposals
from src.utils.feature_proposals import create_proposal as create_feature_proposal
from src.utils.feature_proposals import approve_proposal as approve_feature_proposal
from src.utils.rss_collector import load_sources as rss_load_sources
from src.utils.rss_collector import add_source as rss_add_source
from src.utils.rss_collector import remove_source as rss_remove_source
from src.utils.rss_collector import collect_from_sources as rss_collect
from src.utils.local_doc_ingest import ingest_local_docs_to_clean
from src.utils.local_doc_ingest import build_vector_store_from_clean
from src.utils.local_doc_ingest import load_local_docs_state
from src.utils.local_doc_ingest import process_image_for_learning
from src.utils.local_doc_ingest import ingest_images_from_dirs
from src.utils.provider_selector import get_provider_status
from src.utils.provider_selector import record_provider_score
from src.utils.browser_controller import BrowserController, is_http_url
from src.utils.repo_indexer import index_repository
from src.utils.quality_checks import run_quality_checks
from src.utils.code_search import search_code
from src.utils.apply_history import add_record as add_apply_record
from src.utils.apply_history import list_records as list_apply_records
from live_monitor import LiveMonitor
from idle_mode_dashboard import IdleModeDashboard
from config import Config

app = FastAPI()
assistant = AIAssistant()
_chat_topics: dict[str, dict] = {}
_chat_topic_order: list[str] = []
_chat_topic_counter = 0
_chat_lock = threading.Lock()
index_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "updated_at": None,
}
quality_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "updated_at": None,
}
local_ingest_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "updated_at": None,
}
browser_state = {
    "running": False,
    "last_error": None,
    "updated_at": None,
    "current_url": None,
    "current_title": None,
}
browser = BrowserController()
ocr_watch_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "updated_at": None,
}
_ocr_watch_thread = None

def _safe_path(rel_path: str) -> Path:
    base = Config.BASE_DIR.resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target

def _backup_file(path: Path) -> Path:
    ts = int(time.time())
    backup_dir = Config.BACKUP_DIR / "apply_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.{ts}.bak"
    shutil.copy2(path, backup_path)
    return backup_path

# Allow access from local network or mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def api_access_guard(request: Request, call_next):
    if request.url.path.startswith("/api"):
        # IP allowlist (optional)
        if Config.API_ALLOWED_IPS:
            client_ip = request.client.host if request.client else ""
            if client_ip not in Config.API_ALLOWED_IPS:
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        # Token requirement (optional)
        if Config.API_TOKEN:
            token = request.headers.get("X-API-Key") or request.query_params.get("token")
            if token != Config.API_TOKEN:
                return JSONResponse(status_code=401, content={"detail": "Invalid API token"})
    return await call_next(request)

class Query(BaseModel):
    query: str
    k: int = 4

class Chat(BaseModel):
    message: str

class ChatSendRequest(BaseModel):
    message: str
    topic_id: str | None = None
    force_new: bool = False

class ChatTopicRequest(BaseModel):
    topic_id: str

class ChatTopicRenameRequest(BaseModel):
    topic_id: str
    title: str

class CodeRequest(BaseModel):
    requirement: str
    language: str = "python"

class UIRequest(BaseModel):
    description: str

class Model3DRequest(BaseModel):
    description: str

class TextRequest(BaseModel):
    text: str

class PlanRequest(BaseModel):
    requirement: str

class SummaryRequest(BaseModel):
    days: int = 7

class LocalIngestRequest(BaseModel):
    force: bool = False
    rebuild: bool = True

class ProviderScoreRequest(BaseModel):
    kind: str
    provider: str
    score: float
    notes: str = ""

class BrowserStartRequest(BaseModel):
    headless: bool = True

class BrowserOpenRequest(BaseModel):
    url: str
    wait_ms: int = 1000

class BrowserClickRequest(BaseModel):
    selector: str

class BrowserTypeRequest(BaseModel):
    selector: str
    text: str
    press_enter: bool = False

class BrowserWaitRequest(BaseModel):
    ms: int = 500

class BrowserScreenshotRequest(BaseModel):
    full_page: bool = False

class OcrUploadRequest(BaseModel):
    learn: bool = True
    rebuild: bool = True

class PatchApproveRequest(BaseModel):
    patch_id: str

class LogRequest(BaseModel):
    lines: int = 30
    filter: str = ""
    search: str = ""

class FeatureProposalRequest(BaseModel):
    title: str
    description: str
    requested_by: str = "manual"

class FeatureApproveRequest(BaseModel):
    proposal_id: str

class RssSourceRequest(BaseModel):
    url: str

class RssCollectRequest(BaseModel):
    max_items: int = 0

class IndexRepoRequest(BaseModel):
    max_files: int = 500
    exts: list[str] | None = None

class CodeSearchRequest(BaseModel):
    query: str
    max_files: int = 0
    max_matches: int = 0

class ExplainRequest(BaseModel):
    file: str
    start: int = 1
    end: int = 200
    question: str = ""

class PatchPreviewRequest(BaseModel):
    file: str
    start: int = 1
    end: int = 200
    instruction: str

class ApplyRequest(BaseModel):
    file: str
    start: int = 1
    end: int = 200
    new_code: str

class RestoreRequest(BaseModel):
    backup: str
    file: str


def _build_diff_summary_item(record: dict, max_lines: int = 200) -> dict:
    try:
        import difflib
        file_path = record.get("file")
        backup_path = record.get("backup") or record.get("restored_from")
        if not file_path or not backup_path:
            return {"available": False, "reason": "backup_missing", "record": record}
        target = _safe_path(file_path)
        backup = _safe_path(backup_path)
        if not target.exists() or not backup.exists():
            return {"available": False, "reason": "file_not_found", "record": record}
        old_text = backup.read_text(encoding="utf-8", errors="ignore")
        new_text = target.read_text(encoding="utf-8", errors="ignore")
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff_lines = list(difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", lineterm=""))
        added = 0
        removed = 0
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
        if max_lines > 0 and len(diff_lines) > max_lines:
            preview = "\n".join(diff_lines[:max_lines] + ["... (truncated)"])
        else:
            preview = "\n".join(diff_lines)
        return {
            "available": True,
            "file": file_path,
            "backup": backup_path,
            "ts": record.get("ts"),
            "start": record.get("start"),
            "end": record.get("end"),
            "applied": record.get("applied"),
            "rolled_back": record.get("rolled_back"),
            "restored": record.get("restored"),
            "added": added,
            "removed": removed,
            "diff": preview,
        }
    except Exception as e:
        return {"available": False, "reason": str(e), "record": record}


def _check_token(x_api_key: str = None):
    if Config.API_TOKEN:
        if not x_api_key or x_api_key != Config.API_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid API token")

def _new_topic_id() -> str:
    global _chat_topic_counter
    _chat_topic_counter += 1
    return f"t{int(time.time())}_{_chat_topic_counter}"

def _truncate_title(text: str, limit: int = 24) -> str:
    if not text:
        return "新しい話題"
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"

def _create_topic(title: str | None = None) -> dict:
    topic_id = _new_topic_id()
    ts = time.time()
    topic = {
        "id": topic_id,
        "title": title or "新しい話題",
        "messages": [],
        "created_at": ts,
        "updated_at": ts,
    }
    _chat_topics[topic_id] = topic
    _chat_topic_order.insert(0, topic_id)
    return topic

def _touch_topic(topic: dict):
    topic["updated_at"] = time.time()
    tid = topic["id"]
    if tid in _chat_topic_order:
        _chat_topic_order.remove(tid)
    _chat_topic_order.insert(0, tid)

def _list_topics() -> list[dict]:
    topics = []
    for tid in _chat_topic_order:
        t = _chat_topics.get(tid)
        if not t:
            continue
        topics.append({"id": t["id"], "title": t["title"], "updated_at": t["updated_at"]})
    return topics

def _delete_topic(topic_id: str) -> bool:
    if topic_id in _chat_topics:
        _chat_topics.pop(topic_id, None)
        if topic_id in _chat_topic_order:
            _chat_topic_order.remove(topic_id)
        return True
    return False

@app.post("/api/query")
async def query_rag(q: Query, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    resp = assistant.rag_query(q.query, k=q.k)
    return {"response": resp}


@app.post("/api/chat")
async def chat(q: Chat, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    with _chat_lock:
        topic = _create_topic(_truncate_title(q.message))
        prev_history = list(assistant.llm.conversation_history)
        assistant.llm.conversation_history = []
        resp = assistant.llm.chat(q.message)
        topic["messages"] = list(assistant.llm.conversation_history)
        assistant.llm.conversation_history = prev_history
        _touch_topic(topic)
        return {"response": resp, "topic": {"id": topic["id"], "title": topic["title"]}, "topics": _list_topics()}

@app.post("/api/chat/new")
async def chat_new(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    with _chat_lock:
        topic = _create_topic()
        return {"topic": {"id": topic["id"], "title": topic["title"]}, "topics": _list_topics()}

@app.get("/api/chat/topics")
async def chat_topics(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    with _chat_lock:
        return {"topics": _list_topics()}

@app.get("/api/chat/history")
async def chat_history(topic_id: str, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    with _chat_lock:
        topic = _chat_topics.get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        return {"topic": {"id": topic["id"], "title": topic["title"]}, "messages": topic["messages"]}

@app.post("/api/chat/rename")
async def chat_rename(req: ChatTopicRenameRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    with _chat_lock:
        topic = _chat_topics.get(req.topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic["title"] = title
        _touch_topic(topic)
        return {"topic": {"id": topic["id"], "title": topic["title"]}, "topics": _list_topics()}

@app.post("/api/chat/delete")
async def chat_delete(req: ChatTopicRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    with _chat_lock:
        if not _delete_topic(req.topic_id):
            raise HTTPException(status_code=404, detail="Topic not found")
        return {"topics": _list_topics()}

@app.post("/api/chat/send")
async def chat_send(req: ChatSendRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    if not req.message:
        raise HTTPException(status_code=400, detail="message is required")
    with _chat_lock:
        topic = None
        if req.force_new or not req.topic_id:
            topic = _create_topic()
        else:
            topic = _chat_topics.get(req.topic_id)
            if not topic:
                topic = _create_topic()

        if topic["title"] == "新しい話題":
            topic["title"] = _truncate_title(req.message)

        prev_history = list(assistant.llm.conversation_history)
        assistant.llm.conversation_history = list(topic["messages"])
        resp = assistant.llm.chat(req.message)
        topic["messages"] = list(assistant.llm.conversation_history)
        assistant.llm.conversation_history = prev_history
        _touch_topic(topic)
        return {
            "response": resp,
            "topic": {"id": topic["id"], "title": topic["title"]},
            "topics": _list_topics(),
            "messages": topic["messages"],
        }


@app.get("/api/ping")
async def ping():
    return {"ok": True}


@app.get("/ui", response_class=HTMLResponse)
async def mobile_ui():
        return HTMLResponse(content="""
<!doctype html>
<html lang=\"ja\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <meta http-equiv=\"Cache-Control\" content=\"no-store, no-cache, must-revalidate\" />
    <meta http-equiv=\"Pragma\" content=\"no-cache\" />
    <meta http-equiv=\"Expires\" content=\"0\" />
    <title>AI Assistant Mobile</title>
    <style>
        :root {
            --bg:#0b1020;
            --bg2:#0f172a;
            --bg1:#16213a;
            --bg3:#0a0f1e;
            --card:#121a2b;
            --accent:#6ee7ff;
            --accent2:#8b5cf6;
            --text:#e8ecf1;
            --muted:#98a2b3;
            --header1:#0f1629;
            --header2:#131b33;
            --glow: 0 0 24px rgba(110,231,255,0.2);
        }
        :root[data-theme="light"] {
            --bg:#f5f7fb;
            --bg2:#eef2f7;
            --bg1:#dfe8f5;
            --bg3:#f8fafc;
            --card:#ffffff;
            --accent:#2563eb;
            --accent2:#14b8a6;
            --text:#0f172a;
            --muted:#475569;
            --header1:#e2e8f0;
            --header2:#f1f5f9;
            --glow: 0 0 18px rgba(37,99,235,0.2);
        }
        :root[data-theme="forest"] {
            --bg:#0b1412;
            --bg2:#0f1b18;
            --bg1:#123027;
            --bg3:#07100d;
            --card:#0f1f1a;
            --accent:#34d399;
            --accent2:#22c55e;
            --text:#e6f7f1;
            --muted:#9fb6ad;
            --header1:#0e1a17;
            --header2:#10221d;
            --glow: 0 0 18px rgba(52,211,153,0.22);
        }
        :root[data-theme="mono"] {
            --bg:#0c0c0c;
            --bg2:#151515;
            --bg1:#1f1f1f;
            --bg3:#090909;
            --card:#141414;
            --accent:#e2e8f0;
            --accent2:#94a3b8;
            --text:#f8fafc;
            --muted:#9ca3af;
            --header1:#0f0f0f;
            --header2:#1a1a1a;
            --glow: 0 0 18px rgba(226,232,240,0.18);
        }
        :root[data-theme="cockpit"] {
            --bg:#0a111a;
            --bg2:#0f1a26;
            --bg1:#1a2d3f;
            --bg3:#071018;
            --card:#0e1b2a;
            --accent:#48f0ff;
            --accent2:#7c5cff;
            --text:#eaf6ff;
            --muted:#86a1b8;
            --header1:#0b1723;
            --header2:#132235;
            --glow: 0 0 20px rgba(72,240,255,0.22);
        }
        :root[data-theme="cockpit"] body {
            background:
                repeating-linear-gradient(90deg, rgba(72,240,255,0.06) 0 1px, transparent 1px 42px),
                repeating-linear-gradient(0deg, rgba(124,92,255,0.05) 0 1px, transparent 1px 36px),
                radial-gradient(900px 500px at 50% -20%, rgba(72,240,255,0.08), transparent 60%),
                radial-gradient(700px 500px at 80% 110%, rgba(124,92,255,0.10), transparent 60%),
                radial-gradient(1200px 800px at 10% -10%, var(--bg1) 0%, var(--bg) 55%, var(--bg3) 100%);
        }
        :root[data-theme="cockpit"] header {
            border-bottom:1px solid rgba(72,240,255,0.25);
            box-shadow: 0 4px 24px rgba(72,240,255,0.08);
        }
        :root[data-theme="cockpit"] header h1 {
            letter-spacing:0.8px;
            text-shadow: 0 0 12px rgba(72,240,255,0.45);
        }
        :root[data-theme="cockpit"] .tab {
            border-color: rgba(72,240,255,0.25);
            box-shadow: inset 0 0 12px rgba(72,240,255,0.08);
        }
        :root[data-theme="cockpit"] .tab.active {
            border-color: var(--accent);
            color: var(--accent);
            text-shadow: 0 0 10px rgba(72,240,255,0.6);
        }
        :root[data-theme="cockpit"] .panel {
            position: relative;
            border-color: rgba(72,240,255,0.22);
            background:
                linear-gradient(135deg, rgba(72,240,255,0.06), transparent 40%),
                linear-gradient(225deg, rgba(124,92,255,0.08), transparent 45%),
                var(--card);
            box-shadow: 0 0 20px rgba(72,240,255,0.08), inset 0 0 24px rgba(124,92,255,0.06);
        }
        :root[data-theme="cockpit"] .panel::before {
            content:"";
            position:absolute;
            inset:10px;
            border:1px solid rgba(72,240,255,0.18);
            border-radius:12px;
            pointer-events:none;
            box-shadow: inset 0 0 12px rgba(72,240,255,0.12);
        }
        :root[data-theme="cockpit"] .panel::after {
            content:"";
            position:absolute;
            inset:4px;
            border:1px dashed rgba(124,92,255,0.25);
            border-radius:14px;
            opacity:0.35;
            pointer-events:none;
        }
        :root[data-theme="cockpit"] button {
            background: linear-gradient(135deg, rgba(72,240,255,0.9), rgba(124,92,255,0.9));
            color:#06111c;
            box-shadow: 0 0 14px rgba(72,240,255,0.35), inset 0 0 10px rgba(255,255,255,0.2);
            border:1px solid rgba(72,240,255,0.35);
            border-radius:10px;
        }
        :root[data-theme="cockpit"] .btn-ghost {
            background: rgba(10,17,26,0.6);
            color: var(--text);
            border:1px solid rgba(72,240,255,0.25);
            box-shadow: inset 0 0 10px rgba(72,240,255,0.12);
        }
        :root[data-theme="cockpit"] input,
        :root[data-theme="cockpit"] textarea,
        :root[data-theme="cockpit"] select {
            border-color: rgba(72,240,255,0.25);
            box-shadow: inset 0 0 12px rgba(72,240,255,0.08);
        }
        :root[data-theme="cockpit"] .card {
            border-color: rgba(72,240,255,0.2);
            box-shadow: inset 0 0 10px rgba(72,240,255,0.08);
        }
        :root[data-theme="cockpit"] .footer {
            border-top:1px solid rgba(72,240,255,0.25);
            box-shadow: 0 -8px 24px rgba(72,240,255,0.08);
        }
        body {
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;
            background: radial-gradient(1200px 800px at 10% -10%, var(--bg1) 0%, var(--bg) 55%, var(--bg3) 100%);
            color:var(--text);
        }
        header {
            padding:14px 16px;
            background:linear-gradient(90deg, var(--header1), var(--header2));
            position:sticky; top:0; z-index:2; border-bottom:1px solid #1c2438;
        }
        header h1 { font-size:16px; margin:0; letter-spacing:0.3px; }
        .tabs {
            display:flex; gap:8px; padding:10px 16px; overflow-x:auto;
            background:linear-gradient(180deg, rgba(15,22,41,0.9), rgba(15,22,41,0));
        }
        .tab {
            padding:8px 12px; border-radius:999px; background:rgba(18,26,43,0.85); color:var(--text);
            font-size:12px; border:1px solid #1c2438; cursor:pointer; -webkit-tap-highlight-color: transparent;
            transition:all .2s ease; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
        }
        .tab.active { border-color:var(--accent); color:var(--accent); box-shadow:var(--glow); }
        .container { padding:12px 16px 150px; }
        .panel {
            display:none; background:rgba(18,26,43,0.9); border:1px solid #1c2438; border-radius:16px;
            padding:14px; margin-bottom:12px; box-shadow:0 8px 24px rgba(0,0,0,0.2);
            backdrop-filter: blur(6px);
        }
        .panel.active { display:block; }
        .row { display:flex; gap:8px; }
        input, textarea, select {
            width:100%; background:#0f1629; color:var(--text); border:1px solid #1c2438;
            border-radius:12px; padding:12px; font-size:14px;
        }
        button {
            background:linear-gradient(135deg, var(--accent), var(--accent2)); border:none; color:#00131a;
            padding:10px 12px; border-radius:12px; font-weight:700; font-size:14px; box-shadow:var(--glow);
        }
        .btn-ghost { background:#0f1629; color:var(--text); border:1px solid #1c2438; box-shadow:none; }
        .log, .result { background:#0f1629; border:1px solid #1c2438; border-radius:12px; padding:10px; margin-top:10px; font-size:13px; }
        pre { white-space:pre-wrap; word-break:break-word; margin:0; }
        .cards { display:flex; flex-direction:column; gap:8px; }
        .card { background:#10182a; border:1px solid #1c2438; border-radius:12px; padding:10px; }
        .card h4 { margin:0 0 6px; font-size:14px; color:var(--accent); }
        .kv { display:grid; grid-template-columns: 1fr 1fr; gap:6px; font-size:12px; }
        .chat { display:flex; flex-direction:column; gap:8px; }
        .bubble { max-width:90%; padding:10px 12px; border-radius:12px; font-size:14px; }
        .me { align-self:flex-end; background:#1f2a44; }
        .ai { align-self:flex-start; background:#192033; }
        .footer { position:fixed; bottom:0; left:0; right:0; background:#0f1629; padding:10px; border-top:1px solid #1c2438; }
        .dock { display:flex; flex-direction:column; gap:10px; max-height:45vh; overflow:auto; padding-bottom:4px; }
        .dock button { padding:14px 16px; font-size:16px; border-radius:14px; }
        .dock .row { display:flex; gap:8px; }
        .dock .row.two-col { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
        .dock .row.three-col { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
        .dock .row.two-col button, .dock .row.three-col button { width:100%; }
        .dock input, .dock textarea, .dock select { width:100%; }
        .muted { color:var(--muted); font-size:12px; }
        .quick { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; }
        .chip { padding:8px 10px; border-radius:999px; background:#0f1629; border:1px solid #1c2438; font-size:12px; }
    </style>
</head>
<body>
    <header><h1>AI Assistant Mobile</h1></header>

    <div class=\"tabs\">
        <div class=\"tab active\" data-tab=\"chat\">チャット</div>
        <div class=\"tab\" data-tab=\"gen\">生成</div>
        <div class=\"tab\" data-tab=\"idle\">自己改善</div>
        <div class=\"tab\" data-tab=\"summary\">サマリ</div>
        <div class=\"tab\" data-tab=\"status\">状態</div>
        <div class=\"tab\" data-tab=\"collect\">情報収集</div>
        <div class=\"tab\" data-tab=\"local\">ローカル/OCR</div>
        <div class=\"tab\" data-tab=\"browser\">ブラウザ</div>
        <div class=\"tab\" data-tab=\"index\">索引</div>
        <div class=\"tab\" data-tab=\"quality\">品質</div>
        <div class=\"tab\" data-tab=\"search\">検索</div>
        <div class=\"tab\" data-tab=\"ide\">IDE</div>
        <div class=\"tab\" data-tab=\"patch\">修正</div>
        <div class=\"tab\" data-tab=\"feature\">追加機能</div>
        <div class=\"tab\" data-tab=\"logs\">ログ</div>
        <div class=\"tab\" data-tab=\"dash\">ダッシュボード</div>
    </div>

    <div class="container">
        <div id=\"chat\" class=\"panel active\">
            <div class=\"no-dock\">
                <div class=\"row\">
                    <button id=\"chatNewTopic\">新しい話題</button>
                </div>
                <div class=\"muted\" style=\"margin-top:6px;\">話題一覧</div>
                <div class=\"cards\" id=\"chatTopics\"></div>
            </div>
            <div class=\"chat\" id=\"chatLog\"></div>
            <div class=\"row\" style=\"margin-top:10px;\">
                <textarea id=\"chatInput\" rows=\"3\" placeholder=\"ここに質問を入力（改行可）\"></textarea>
                <button id=\"chatSend\">送信</button>
            </div>
            <div class=\"row\" style=\"margin-top:6px;\">
                <label class=\"muted\"><input id=\"chatContinue\" type=\"checkbox\" /> 続きで送信</label>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">チャットはここで送信</div>
        </div>

        <div id=\"gen\" class=\"panel\">
            <div class=\"row\">
                <select id=\"genType\">
                    <option value=\"code\">コード生成</option>
                    <option value=\"ui\">UI生成</option>
                    <option value=\"3d\">3D生成</option>
                    <option value=\"summary\">要約</option>
                    <option value=\"plan\">実装計画</option>
                </select>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">目的に合わせて生成タイプを選択</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <select id=\"codeLang\">
                    <option value=\"python\">Python</option>
                    <option value=\"javascript\">JavaScript</option>
                    <option value=\"html\">HTML</option>
                </select>
            </div>
            <textarea id=\"genInput\" rows=\"4\" placeholder=\"生成したい内容\" style=\"margin-top:8px;\"></textarea>
            <button id=\"genBtn\" style=\"margin-top:8px;\">生成を実行</button>
            <div class=\"result\" id=\"genOut\"></div>
        </div>

        <div id=\"idle\" class=\"panel\">
            <div class=\"row two-col\">
                <button id=\"idleStart\">自己改善開始</button>
                <button id=\"idleStop\">自己改善停止</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <button id=\"idleStatus\">状態を取得</button>
                <button id=\"idleRestart\">再起動</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">放置モード（自己改善）の開始/停止/状態確認</div>
            <div class=\"result\" id=\"idleOut\"></div>
        </div>

        <div id=\"summary\" class=\"panel\">
            <div class=\"row\">
                <input id=\"summaryDays\" type=\"number\" value=\"7\" min=\"1\" />
                <button id=\"summaryBtn\">日次を取得</button>
                <button id=\"summaryAll\" style=\"margin-left:6px;\">全期間を取得</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">学習のサマリや変化を確認</div>
            <div class=\"cards\" id=\"summaryOut\"></div>
        </div>

        <div id=\"status\" class=\"panel\">
            <div class=\"row\">
                <button id=\"statusBtn\">システム状態を取得</button>
                <button id=\"healthBtn\" style=\"margin-left:6px;\">ヘルスチェック</button>
                <button id=\"healBtn\" style=\"margin-left:6px;\">自動復旧</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <select id=\"uiTheme\">
                    <option value=\"default\">デフォルト</option>
                    <option value=\"light\">ライト</option>
                    <option value=\"forest\">フォレスト</option>
                    <option value=\"mono\">モノクロ</option>
                    <option value=\"cockpit\">コックピット</option>
                </select>
                <button id=\"uiThemeApply\">テーマ適用</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">UIテーマを切り替え</div>
            <div class=\"muted\" style=\"margin-top:6px;\">稼働/学習の状態を確認</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <label class=\"muted\"><input id=\"statusAuto\" type=\"checkbox\" /> 自動更新(30秒)</label>
            </div>
            <div class=\"result\" id=\"statusOut\"></div>
            <div class=\"row\" style=\"margin-top:12px;\">
                <button id=\"providerStatus\">プロバイダ状態</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"providerKind\" placeholder=\"種別 (llm/ocr)\" />
                <input id=\"providerName\" placeholder=\"プロバイダ名\" style=\"margin-left:6px;\" />
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"providerScore\" type=\"number\" min=\"0\" max=\"1\" step=\"0.01\" placeholder=\"スコア(0-1)\" />
                <input id=\"providerNotes\" placeholder=\"メモ(任意)\" style=\"margin-left:6px;\" />
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <button id=\"providerSave\">スコア登録</button>
            </div>
            <div class=\"result\" id=\"providerOut\"></div>
        </div>

        <div id=\"collect\" class=\"panel\">
            <div class=\"row\">
                <input id=\"rssUrl\" placeholder=\"RSS/Atom URL\" />
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">RSSを追加/削除し、収集して学習に回す</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <button id=\"rssAdd\">追加</button>
                <button id=\"rssRemove\" style=\"margin-left:6px;\">削除</button>
                <button id=\"rssList\" style=\"margin-left:6px;\">一覧</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"rssMax\" type=\"number\" value=\"30\" min=\"1\" />
                <button id=\"rssCollect\" style=\"margin-left:6px;\">収集してwatchlistへ</button>
            </div>
            <div class=\"result\" id=\"rssOut\"></div>
        </div>

        <div id=\"local\" class=\"panel\">
            <div class=\"row\">
                <label class=\"muted\"><input id=\"localForce\" type=\"checkbox\" /> クールダウン無視</label>
                <label class=\"muted\" style=\"margin-left:10px;\"><input id=\"localRebuild\" type=\"checkbox\" checked /> ベクトル再構築</label>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"ocrFile\" type=\"file\" accept=\"image/*\" />
            </div>
            <div class=\"row two-col\" style=\"margin-top:8px;\">
                <button id=\"ocrUpload\">OCRして表示</button>
                <button id=\"ocrUploadLearn\">OCRして学習</button>
            </div>
            <div class=\"row two-col\" style=\"margin-top:8px;\">
                <button id=\"localRun\">ローカル学習を実行</button>
                <button id=\"localStatus\">状態</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">スクリーンショット/画像はOCRで文字化して学習</div>
            <div class=\"row three-col\" style=\"margin-top:8px;\">
                <button id=\"ocrWatchStart\">監視開始</button>
                <button id=\"ocrWatchStop\">監視停止</button>
                <button id=\"ocrWatchStatus\">監視状態</button>
            </div>
            <div class=\"result\" id=\"localOut\"></div>
        </div>

        <div id=\"browser\" class=\"panel\">
            <div class=\"row\">
                <button id=\"browserStart\">開始</button>
                <button id=\"browserStop\" style=\"margin-left:6px;\">停止</button>
                <button id=\"browserStatus\" style=\"margin-left:6px;\">状態</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"browserUrl\" placeholder=\"https://example.com\" />
                <button id=\"browserOpen\" style=\"margin-left:6px;\">開く</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"browserSelector\" placeholder=\"CSSセレクタ\" />
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <button id=\"browserClick\">クリック</button>
                <button id=\"browserWait\" style=\"margin-left:6px;\">待機(500ms)</button>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"browserText\" placeholder=\"入力テキスト\" />
                <button id=\"browserType\" style=\"margin-left:6px;\">入力</button>
                <label class=\"muted\" style=\"margin-left:6px;\"><input id=\"browserEnter\" type=\"checkbox\" /> Enter</label>
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <button id=\"browserTextGet\">テキスト取得</button>
                <button id=\"browserShot\" style=\"margin-left:6px;\">スクショ</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">robots.txtや利用規約を尊重して操作してください</div>
            <div class=\"result\" id=\"browserOut\"></div>
        </div>

        <div id=\"index\" class=\"panel\">
            <div class=\"row\">
                <input id=\"indexMaxFiles\" type=\"number\" value=\"500\" min=\"1\" />
                <button id=\"indexRepo\" style=\"margin-left:6px;\">リポジトリ索引</button>
                <button id=\"indexStatus\" style=\"margin-left:6px;\">状態</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">.py/.md/.txt/.json/.yml/.yaml を索引化</div>
            <div class=\"result\" id=\"indexOut\"></div>
        </div>

        <div id=\"quality\" class=\"panel\">
            <div class=\"row\">
                <button id=\"qualityRun\">品質チェック実行</button>
                <button id=\"qualityStatus\" style=\"margin-left:6px;\">状態</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">compileall / pytest (存在時) を実行</div>
            <div class=\"result\" id=\"qualityOut\"></div>
        </div>

        <div id=\"search\" class=\"panel\">
            <div class=\"row\">
                <input id=\"searchQuery\" placeholder=\"検索キーワード\" />
                <button id=\"searchBtn\" style=\"margin-left:6px;\">検索</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">リポジトリ内のテキスト検索</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"searchMaxFiles\" type=\"number\" value=\"200\" min=\"1\" />
                <input id=\"searchMaxMatches\" type=\"number\" value=\"50\" min=\"1\" style=\"margin-left:6px;\" />
            </div>
            <div class=\"result\" id=\"searchOut\"></div>
        </div>

        <div id=\"ide\" class=\"panel\">
            <div class=\"row\">
                <input id=\"ideQuery\" placeholder=\"コード検索キーワード\" />
                <button id=\"ideSearch\" style=\"margin-left:6px;\">検索</button>
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">コード説明/提案/適用/履歴管理</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"ideFile\" placeholder=\"説明するファイル (例: api.py)\" />
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"ideStart\" type=\"number\" value=\"1\" min=\"1\" />
                <input id=\"ideEnd\" type=\"number\" value=\"200\" min=\"1\" style=\"margin-left:6px;\" />
            </div>
            <textarea id=\"ideQuestion\" rows=\"3\" placeholder=\"何を知りたいか (任意)\" style=\"margin-top:8px;\"></textarea>
            <button id=\"ideExplain\" style=\"margin-top:8px;\">説明</button>
            <textarea id=\"ideInstruction\" rows=\"3\" placeholder=\"提案したい変更内容\" style=\"margin-top:8px;\"></textarea>
            <button id=\"ideSuggest\" style=\"margin-top:8px;\">提案と差分</button>
            <textarea id=\"ideNewCode\" rows=\"6\" placeholder=\"適用する新しいコード（提案結果を貼り付け）\" style=\"margin-top:8px;\"></textarea>
            <button id=\"ideApply\" style=\"margin-top:8px;\">適用</button>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"ideDiffLimit\" type=\"number\" value=\"20\" min=\"1\" />
                <input id=\"ideDiffMaxLines\" type=\"number\" value=\"200\" min=\"1\" style=\"margin-left:6px;\" />
            </div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <select id=\"ideDiffSort\">
                    <option value=\"time_desc\">新しい順</option>
                    <option value=\"impact_desc\">変更量が多い順</option>
                </select>
            </div>
            <input id=\"ideDiffFilter\" placeholder=\"ファイル名フィルタ (任意)\" style=\"margin-top:8px;\" />
            <button id=\"ideDiffSummary\" style=\"margin-top:8px;\">差分一覧</button>
            <button id=\"ideHistory\" style=\"margin-top:8px;\">履歴/バックアップ</button>
            <input id=\"ideBackup\" placeholder=\"復元するバックアップファイル\" style=\"margin-top:8px;\" />
            <button id=\"ideRestore\" style=\"margin-top:8px;\">復元</button>
            <div class=\"result\" id=\"ideOut\"></div>
        </div>

        <div id=\"patch\" class=\"panel\">
            <button id=\"patchList\">一覧を取得</button>
            <div class=\"muted\" style=\"margin-top:6px;\">提案パッチの確認と承認</div>
            <div class=\"row\" style=\"margin-top:8px;\">
                <input id=\"patchId\" placeholder=\"patch_id\" />
                <button id=\"patchApprove\">承認を実行</button>
            </div>
            <div class=\"result\" id=\"patchOut\"></div>
        </div>

        <div id=\"feature\" class=\"panel\">
            <div class=\"row\">
                <input id=\"featureTitle\" placeholder=\"追加機能のタイトル\" />
            </div>
            <div class=\"muted\" style=\"margin-top:6px;\">機能提案の作成/承認</div>
            <textarea id=\"featureDesc\" rows=\"3\" placeholder=\"追加機能の内容\" style=\"margin-top:8px;\"></textarea>
            <button id=\"featurePropose\" style=\"margin-top:8px;\">提案を作成</button>
            <div class=\"row\" style=\"margin-top:8px;\">
            <div class=\"row two-col\" style=\"margin-top:8px;\">
                <input id=\"featureId\" placeholder=\"proposal_id\" />
                <button id=\"featureApprove\">承認</button>
            </div>
            <div class=\"row two-col\" style=\"margin-top:8px;\">
                <button id=\"localRun\">ローカル学習を実行</button>
                <button id=\"localStatus\">状態</button>
            </div>
            <div class=\"row three-col\" style=\"margin-top:8px;\">
                <button id=\"ocrWatchStart\">監視開始</button>
                <button id=\"ocrWatchStop\">監視停止</button>
                <button id=\"ocrWatchStatus\">監視状態</button>
            </div>
                <button id=\"logTail\">最新ログ取得</button>
                <input id=\"logSearch\" placeholder=\"検索キーワード\" />
                <button id=\"logSearchBtn\">検索</button>
            </div>
            <div class=\"result\" id=\"logOut\"></div>
        </div>

        <div id=\"dash\" class=\"panel\">
            <button id=\"dashOpen\">HTMLダッシュボードを表示</button>
            <div class=\"muted\" style=\"margin-top:6px;\">詳細なメトリクスを別画面で表示</div>
            <div class=\"result\" id=\"dashOut\"></div>
        </div>

    </div>

    <div class=\"footer\">
        <div class=\"muted\">/ui からアクセス（同一LAN内）</div>
        <div id=\"inputDock\" class=\"dock\" style=\"margin-top:8px;\"></div>
        <div id=\"statusToast\" class=\"muted\" style=\"margin-top:4px;\">状態: 読み込み中...</div>
        <div id=\"jsBoot\" class=\"muted\" style=\"margin-top:4px;\">JS: 未実行</div>
    </div>

    <noscript>
        <div style=\"padding:12px; color:#ffb4a2;\">JavaScriptが無効です。ブラウザ設定で有効にしてください。</div>
    </noscript>

<script>
(function(){
    function _dummyEl(){
        return {
            value: '',
            checked: false,
            textContent: '',
            innerHTML: '',
            classList: { add: function(){}, remove: function(){} },
            appendChild: function(){},
            scrollTop: 0,
            scrollHeight: 0
        };
    }
    function byId(id){ return document.getElementById(id) || _dummyEl(); }
    function setStatus(msg){ byId('statusToast').textContent = '状態: ' + msg; }
    function escapeHtml(str){
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function renderKV(obj){
        if (!obj){ return '<div class="card">情報なし</div>'; }
        var html = '<div class="kv">';
        for (var k in obj){
            if (!Object.prototype.hasOwnProperty.call(obj, k)) continue;
            var v = obj[k];
            if (v === null || v === undefined) v = '';
            else if (Array.isArray(v)) v = '件数 ' + v.length;
            else if (typeof v === 'object') v = '（詳細あり）';
            html += '<div>' + escapeHtml(k) + '</div><div>' + escapeHtml(String(v)) + '</div>';
        }
        html += '</div>';
        return html;
    }
    function renderCard(title, body){
        return '<div class="card"><h4>' + escapeHtml(title) + '</h4>' + body + '</div>';
    }

    function api(path, method, body, cb){
        var xhr = new XMLHttpRequest();
        xhr.open(method, path, true);
        xhr.setRequestHeader('Content-Type','application/json');
        xhr.onreadystatechange = function(){
            if (xhr.readyState === 4){
                if (xhr.status >= 200 && xhr.status < 300) {
                    try { cb(JSON.parse(xhr.responseText || '{}')); }
                    catch(e){ cb({}); }
                } else {
                    setStatus('通信エラー ' + xhr.status);
                    try { cb(JSON.parse(xhr.responseText || '{}')); }
                    catch(e){ cb({}); }
                }
            }
        };
        xhr.onerror = function(){ setStatus('通信エラー'); };
        xhr.send(body ? JSON.stringify(body) : null);
    }

    function upload(path, formData, cb){
        var xhr = new XMLHttpRequest();
        xhr.open('POST', path, true);
        xhr.onreadystatechange = function(){
            if (xhr.readyState === 4){
                if (xhr.status >= 200 && xhr.status < 300) {
                    try { cb(JSON.parse(xhr.responseText || '{}')); }
                    catch(e){ cb({}); }
                } else {
                    setStatus('通信エラー ' + xhr.status);
                    try { cb(JSON.parse(xhr.responseText || '{}')); }
                    catch(e){ cb({}); }
                }
            }
        };
        xhr.onerror = function(){ setStatus('通信エラー'); };
        xhr.send(formData);
    }

    window.onerror = function(msg){ setStatus('エラー: ' + msg); };

    function collectDockNodes(panel){
        var nodes = [];
        if (!panel || !panel.children) return nodes;
        var children = Array.prototype.slice.call(panel.children);
        for (var i=0;i<children.length;i++){
            var child = children[i];
            if (child && child.classList && child.classList.contains('no-dock')){
                continue;
            }
            if (!child || !child.querySelector) continue;
            if (child.classList && (child.classList.contains('result') || child.classList.contains('cards'))) {
                continue;
            }
            if ((child.matches && child.matches('input, textarea, select, button'))
                || (child.querySelector && child.querySelector('input, textarea, select, button'))){
                nodes.push(child);
            }
        }
        return nodes;
    }

    function restoreAllDocked(){
        var dock = byId('inputDock');
        if (!dock) return;
        var nodes = Array.prototype.slice.call(dock.children || []);
        for (var i=0;i<nodes.length;i++){
            var node = nodes[i];
            if (node && node.__dockMarker && node.__dockMarker.parentNode){
                node.__dockMarker.parentNode.insertBefore(node, node.__dockMarker);
                node.__dockMarker.parentNode.removeChild(node.__dockMarker);
                node.__dockMarker = null;
                node.removeAttribute('data-docked');
            }
        }
        dock.innerHTML = '';
    }

    function dockPanel(panelId){
        var dock = byId('inputDock');
        if (!dock || !panelId) return;
        restoreAllDocked();
        var panel = byId(panelId);
        var nodes = collectDockNodes(panel);
        dock.innerHTML = '';
        for (var i=0;i<nodes.length;i++){
            var node = nodes[i];
            if (!node.__dockMarker){
                var marker = document.createComment('dock');
                node.__dockMarker = marker;
                if (node.parentNode){
                    node.parentNode.insertBefore(marker, node);
                }
            }
            node.setAttribute('data-docked', 'true');
            dock.appendChild(node);
        }
    }

    function getTheme(){
        try { return localStorage.getItem('uiTheme') || 'default'; } catch(e){ return 'default'; }
    }

    function setTheme(name){
        var theme = name || 'default';
        if (theme === 'default') {
            document.documentElement.removeAttribute('data-theme');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }

    function boot(){
        var jsBoot = byId('jsBoot');
        if (jsBoot) jsBoot.textContent = 'JS: 起動';
        setStatus('UI準備完了');
        var themeSelect = byId('uiTheme');
        var themeApply = byId('uiThemeApply');
        var currentTheme = getTheme();
        setTheme(currentTheme);
        if (themeSelect) themeSelect.value = currentTheme;
        if (themeApply) themeApply.onclick = function(){
            var v = (themeSelect.value || 'default').trim();
            try { localStorage.setItem('uiTheme', v); } catch(e) {}
            setTheme(v);
            setStatus('テーマ変更済み');
        };
        api('/api/ping','GET',null,function(data){
            if (data && data.ok) setStatus('接続OK');
        });
        dockPanel('chat');
        newTopic();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    try {
        var tabs = document.querySelectorAll('.tab');
        for (var i=0;i<tabs.length;i++){
            tabs[i].onclick = (function(t){
                return function(){
                    for (var j=0;j<tabs.length;j++){ tabs[j].classList.remove('active'); }
                    t.classList.add('active');
                    var panels = document.querySelectorAll('.panel');
                    for (var k=0;k<panels.length;k++){ panels[k].classList.remove('active'); }
                    var id = t.getAttribute('data-tab');
                    byId(id).classList.add('active');
                    dockPanel(id);
                };
            })(tabs[i]);
        }
    } catch (e) {
        setStatus('エラー: ' + (e && e.message ? e.message : e));
    }

    // Chat
    var chatLog = byId('chatLog');
    var chatInput = byId('chatInput');
    var chatTopics = byId('chatTopics');
    var chatContinue = byId('chatContinue');
    var chatNewTopicBtn = byId('chatNewTopic');
    var currentTopicId = null;

    function renderTopics(list){
        if (!chatTopics){ return; }
        if (!list || list.length === 0){
            chatTopics.innerHTML = '<div class="card">話題がありません</div>';
            return;
        }
        var html = '';
        for (var i=0;i<list.length;i++){
            var t = list[i];
            var title = t.title || '新しい話題';
            html += '<div class="card" style="cursor:pointer" data-topic-id="' + escapeHtml(t.id) + '">'
                + '<div class="muted" style="font-size:11px;">' + escapeHtml(t.id) + '</div>'
                + '<div>' + escapeHtml(title) + '</div>'
                + '<div class="row" style="margin-top:6px; gap:6px;">'
                + '<button data-topic-rename="' + escapeHtml(t.id) + '" class="btn-ghost">名前変更</button>'
                + '<button data-topic-delete="' + escapeHtml(t.id) + '" class="btn-ghost">削除</button>'
                + '</div>'
                + '</div>';
        }
        chatTopics.innerHTML = html;
        var cards = chatTopics.querySelectorAll('[data-topic-id]');
        for (var j=0;j<cards.length;j++){
            cards[j].onclick = function(){
                var tid = this.getAttribute('data-topic-id');
                if (!tid) return;
                currentTopicId = tid;
                if (chatContinue) chatContinue.checked = true;
                loadHistory(tid);
            };
        }
        var renameBtns = chatTopics.querySelectorAll('[data-topic-rename]');
        for (var r=0;r<renameBtns.length;r++){
            renameBtns[r].onclick = function(e){
                e.stopPropagation();
                var tid = this.getAttribute('data-topic-rename');
                if (!tid) return;
                var newTitle = window.prompt('話題名を変更', '');
                if (!newTitle) return;
                api('/api/chat/rename','POST',{topic_id: tid, title: newTitle}, function(data){
                    renderTopics(data.topics || []);
                });
            };
        }
        var deleteBtns = chatTopics.querySelectorAll('[data-topic-delete]');
        for (var d=0;d<deleteBtns.length;d++){
            deleteBtns[d].onclick = function(e){
                e.stopPropagation();
                var tid = this.getAttribute('data-topic-delete');
                if (!tid) return;
                if (!window.confirm('この話題を削除しますか？')) return;
                api('/api/chat/delete','POST',{topic_id: tid}, function(data){
                    if (currentTopicId === tid){
                        currentTopicId = null;
                        setChatLog([]);
                        if (chatContinue) chatContinue.checked = false;
                    }
                    renderTopics(data.topics || []);
                });
            };
        }
    }

    function loadTopics(){
        api('/api/chat/topics','GET',null,function(data){
            renderTopics(data.topics || []);
        });
    }

    function setChatLog(messages){
        if (!chatLog){ return; }
        chatLog.innerHTML = '';
        if (!messages || messages.length === 0){ return; }
        for (var i=0;i<messages.length;i++){
            var m = messages[i];
            var cls = (m.role === 'user') ? 'me' : 'ai';
            addBubble(m.content || '', cls);
        }
    }

    function loadHistory(topicId){
        if (!topicId) return;
        api('/api/chat/history?topic_id=' + encodeURIComponent(topicId),'GET',null,function(data){
            setChatLog(data.messages || []);
            if (data.topic && data.topic.id){
                currentTopicId = data.topic.id;
            }
        });
    }

    function newTopic(){
        api('/api/chat/new','POST',null,function(data){
            if (data.topic && data.topic.id){
                currentTopicId = data.topic.id;
                setChatLog([]);
            }
            if (chatContinue) chatContinue.checked = false;
            renderTopics(data.topics || []);
        });
    }

    if (chatNewTopicBtn) {
        chatNewTopicBtn.onclick = function(){
            newTopic();
        };
    }

    byId('chatSend').onclick = function(){
        var msg = (chatInput.value || '').trim();
        if (!msg) return;
        addBubble(msg, 'me');
        chatInput.value = '';
        setStatus('チャット送信中...');
        var forceNew = !(chatContinue && chatContinue.checked);
        api('/api/chat/send','POST',{message: msg, topic_id: currentTopicId, force_new: forceNew}, function(data){
            addBubble(data.response || '（応答なし）', 'ai');
            if (data.topic && data.topic.id){
                currentTopicId = data.topic.id;
            }
            renderTopics(data.topics || []);
            setStatus('チャット完了');
        });
    };

    function addBubble(text, cls){
        var div = document.createElement('div');
        div.className = 'bubble ' + cls;
        div.textContent = text;
        chatLog.appendChild(div);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // Generation
    byId('genBtn').onclick = function(){
        var type = byId('genType').value;
        var input = (byId('genInput').value || '').trim();
        if (!input) return;
        setStatus('生成実行中...');
        var path = '/api/generate/code';
        var body = {requirement: input, language: (byId('codeLang').value || 'python')};
        if (type === 'ui'){ path = '/api/generate/ui'; body = {description: input}; }
        if (type === '3d'){ path = '/api/generate/3d'; body = {description: input}; }
        if (type === 'summary'){ path = '/api/generate/summary'; body = {text: input}; }
        if (type === 'plan'){ path = '/api/generate/plan'; body = {requirement: input}; }
        api(path,'POST',body,function(data){
            var content = data.code || data.html || data.scene || data.summary || data.plan;
            if (!content){
                content = '結果を表示できませんでした。';
            }
            byId('genOut').innerHTML = '<pre>' + escapeHtml(content) + '</pre>';
            setStatus('生成完了');
        });
    };
    // Idle
    byId('idleStart').onclick = function(){
        setStatus('放置モード開始...');
        api('/api/idle/start','POST',null,function(data){
            byId('idleOut').innerHTML = '<pre>' + escapeHtml(formatIdle(data)) + '</pre>';
            setStatus('開始完了');
        });
    };
    byId('idleStop').onclick = function(){
        setStatus('放置モード停止...');
        api('/api/idle/stop','POST',null,function(data){
            byId('idleOut').innerHTML = '<pre>' + escapeHtml(formatIdle(data)) + '</pre>';
            setStatus('停止完了');
        });
    };
    byId('idleStatus').onclick = function(){
        setStatus('状態取得中...');
        api('/api/idle/status','GET',null,function(data){
            byId('idleOut').innerHTML = '<pre>' + escapeHtml(formatIdle(data)) + '</pre>';
            setStatus('取得完了');
        });
    };
    byId('idleRestart').onclick = function(){
        setStatus('放置モード再起動中...');
        api('/api/idle/restart','POST',null,function(data){
            byId('idleOut').innerHTML = '<pre>' + escapeHtml(formatIdle(data)) + '</pre>';
            setStatus('再起動完了');
        });
    };

    // Summary
    byId('summaryBtn').onclick = function(){
        var days = parseInt(byId('summaryDays').value || '7', 10);
        setStatus('日次サマリ取得中...');
        api('/api/summary/daily','POST',{days: days}, function(data){
            renderSummary(data);
            setStatus('日次サマリ取得完了');
        });
    };
    byId('summaryAll').onclick = function(){
        setStatus('全期間サマリ取得中...');
        api('/api/summary/all','GET',null, function(data){
            renderSummary(data);
            setStatus('全期間サマリ取得完了');
        });
    };

    // Status
    var statusTimer = null;
    function renderStatus(data){
        var out = byId('statusOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var html = '';
        html += renderCard('放置モード', renderKV(data.idle || {}));
        html += renderCard('ワーカー', renderKV(data.worker || {}));
        html += renderCard('監視', renderKV(data.monitor || {}));
        html += renderCard('稼働時間', renderKV({uptime: data.uptime || ''}));
        html += renderCard('学習', renderKV(data.learning || {}));
        html += renderCard('ベクトルストア', renderKV(data.vector_store || {}));
        out.innerHTML = html;
    }
    function renderHealth(data){
        var out = byId('statusOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var ok = data.ok ? 'OK' : 'NG';
        var html = '';
        html += renderCard('ヘルス', renderKV({ok: ok}));
        html += renderCard('詳細', renderKV(data));
        out.innerHTML = html;
    }
    function renderHealResult(data){
        var out = byId('statusOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var html = '';
        html += renderCard('自動復旧', renderKV({healed: data.healed, action: data.action}));
        html += renderCard('復旧前', renderKV(data.before || {}));
        html += renderCard('復旧後', renderKV(data.after || {}));
        out.innerHTML = html;
    }
    function fetchStatus(){
        setStatus('状態取得中...');
        api('/api/status','GET',null,function(data){
            renderStatus(data);
            setStatus('状態取得完了');
        });
    }
    function fetchHealth(){
        setStatus('ヘルスチェック中...');
        api('/api/health','GET',null,function(data){
            renderHealth(data);
            setStatus('ヘルスチェック完了');
        });
    }
    function runHeal(){
        setStatus('自動復旧中...');
        api('/api/heal','POST',null,function(data){
            renderHealResult(data);
            setStatus('自動復旧完了');
        });
    }
    byId('statusBtn').onclick = fetchStatus;
    byId('healthBtn').onclick = fetchHealth;
    byId('healBtn').onclick = runHeal;
    byId('statusAuto').onchange = function(){
        if (statusTimer){ clearInterval(statusTimer); statusTimer = null; }
        if (this.checked){
            fetchHealth();
            statusTimer = setInterval(fetchHealth, 30000);
        }
    };

    // Provider status / scoring
    function renderProviderOut(data){
        var out = byId('providerOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var html = '';
        if (data.llm){ html += renderCard('LLM', renderKV({selected: data.llm.selected})); }
        if (data.ocr){ html += renderCard('OCR', renderKV({selected: data.ocr.selected})); }
        if (data.ok === true || data.ok === false){
            html += renderCard('登録結果', renderKV({ok: data.ok, scores: data.scores ? '更新済み' : ''}));
        }
        out.innerHTML = html || '<div class="card">情報なし</div>';
    }
    byId('providerStatus').onclick = function(){
        setStatus('プロバイダ状態取得中...');
        api('/api/providers/status','GET',null,function(data){
            renderProviderOut(data);
            setStatus('プロバイダ状態取得完了');
        });
    };
    byId('providerSave').onclick = function(){
        var kind = (byId('providerKind').value || '').trim();
        var provider = (byId('providerName').value || '').trim();
        var score = parseFloat(byId('providerScore').value || '0');
        var notes = (byId('providerNotes').value || '').trim();
        if (!kind || !provider){ return; }
        setStatus('プロバイダスコア登録中...');
        api('/api/providers/score','POST',{kind: kind, provider: provider, score: score, notes: notes},function(data){
            renderProviderOut(data);
            setStatus('プロバイダスコア登録完了');
        });
    };

    // RSS Collection
    function renderRssList(list){
        var out = byId('rssOut');
        if (!list || list.length === 0){
            out.innerHTML = '<div class="card">登録済みソースはありません</div>';
            return;
        }
        var html = '';
        for (var i=0;i<list.length;i++){
            html += '<div class="card">' + escapeHtml(list[i]) + '</div>';
        }
        out.innerHTML = html;
    }
    byId('rssList').onclick = function(){
        setStatus('RSS一覧取得中...');
        api('/api/rss/list','GET',null,function(data){
            renderRssList(data.sources || []);
            setStatus('RSS一覧取得完了');
        });
    };
    byId('rssAdd').onclick = function(){
        var url = (byId('rssUrl').value || '').trim();
        if (!url) return;
        setStatus('RSS追加中...');
        api('/api/rss/add','POST',{url: url},function(data){
            renderRssList(data.sources || []);
            setStatus('RSS追加完了');
        });
    };
    byId('rssRemove').onclick = function(){
        var url = (byId('rssUrl').value || '').trim();
        if (!url) return;
        setStatus('RSS削除中...');
        api('/api/rss/remove','POST',{url: url},function(data){
            renderRssList(data.sources || []);
            setStatus('RSS削除完了');
        });
    };
    byId('rssCollect').onclick = function(){
        var maxItems = parseInt(byId('rssMax').value || '0', 10);
        setStatus('RSS収集中...');
        api('/api/rss/collect','POST',{max_items: maxItems},function(data){
            var out = byId('rssOut');
            var added = (data && data.added) ? data.added : 0;
            var count = (data && data.count) ? data.count : 0;
            out.innerHTML = renderCard('収集結果', renderKV({added: added, total: count}));
            setStatus('RSS収集完了');
        });
    };

    // Local OCR ingest
    function renderLocalStatus(data){
        var out = byId('localOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var html = '';
        if (data.state){ html += renderCard('実行状態', renderKV(data.state)); }
        if (data.last_state){ html += renderCard('前回結果', renderKV(data.last_state)); }
        if (data.ocr){ html += renderCard('OCR設定', renderKV(data.ocr)); }
        if (data.text){ html += renderCard('OCR結果', '<pre>' + escapeHtml(data.text) + '</pre>'); }
        if (data.clean_file){ html += renderCard('学習保存先', renderKV({file: data.clean_file})); }
        out.innerHTML = html || '<div class="card">情報なし</div>';
    }
    byId('localStatus').onclick = function(){
        setStatus('ローカル学習の状態取得中...');
        api('/api/local/status','GET',null,function(data){
            renderLocalStatus(data);
            setStatus('ローカル学習の状態取得完了');
        });
    };
    byId('localRun').onclick = function(){
        var force = !!byId('localForce').checked;
        var rebuild = !!byId('localRebuild').checked;
        setStatus('ローカル学習を実行中...');
        api('/api/local/ingest','POST',{force: force, rebuild: rebuild},function(data){
            renderLocalStatus(data);
            setStatus('ローカル学習実行完了');
        });
    };

    byId('ocrUpload').onclick = function(){
        var file = byId('ocrFile').files[0];
        if (!file) return;
        setStatus('OCR実行中...');
        var fd = new FormData();
        fd.append('file', file);
        fd.append('learn', 'false');
        fd.append('rebuild', 'false');
        upload('/api/ocr/upload', fd, function(data){
            renderLocalStatus(data);
            setStatus('OCR完了');
        });
    };
    byId('ocrUploadLearn').onclick = function(){
        var file = byId('ocrFile').files[0];
        if (!file) return;
        setStatus('OCRして学習中...');
        var fd = new FormData();
        fd.append('file', file);
        fd.append('learn', 'true');
        fd.append('rebuild', String(!!byId('localRebuild').checked));
        upload('/api/ocr/upload', fd, function(data){
            renderLocalStatus(data);
            setStatus('OCR学習完了');
        });
    };

    byId('ocrWatchStart').onclick = function(){
        setStatus('OCR監視開始中...');
        api('/api/ocr/watch/start','POST',null,function(data){
            renderLocalStatus(data);
            setStatus('OCR監視開始');
        });
    };
    byId('ocrWatchStop').onclick = function(){
        setStatus('OCR監視停止中...');
        api('/api/ocr/watch/stop','POST',null,function(data){
            renderLocalStatus(data);
            setStatus('OCR監視停止');
        });
    };
    byId('ocrWatchStatus').onclick = function(){
        setStatus('OCR監視状態取得中...');
        api('/api/ocr/watch/status','GET',null,function(data){
            renderLocalStatus(data);
            setStatus('OCR監視状態取得完了');
        });
    };

    // Browser automation
    function renderBrowserOut(data){
        var out = byId('browserOut');
        if (!data){ out.innerHTML = '<div class="card">情報なし</div>'; return; }
        var html = '';
        if (data.info){
            html += renderCard('ページ情報', renderKV(data.info));
        }
        if (data.text){
            html += renderCard('テキスト', '<pre>' + escapeHtml(String(data.text).slice(0, 800)) + '</pre>');
        }
        if (data.path){
            html += renderCard('スクリーンショット', renderKV({path: data.path}));
        }
        if (!html){
            html = renderCard('結果', renderKV(data));
        }
        out.innerHTML = html;
    }
    byId('browserStart').onclick = function(){
        setStatus('ブラウザ開始中...');
        api('/api/browser/start','POST',{headless: true},function(data){
            renderBrowserOut(data);
            setStatus('ブラウザ開始完了');
        });
    };
    byId('browserStop').onclick = function(){
        setStatus('ブラウザ停止中...');
        api('/api/browser/stop','POST',null,function(data){
            renderBrowserOut(data);
            setStatus('ブラウザ停止完了');
        });
    };
    byId('browserStatus').onclick = function(){
        setStatus('ブラウザ状態取得中...');
        api('/api/browser/status','GET',null,function(data){
            renderBrowserOut(data);
            setStatus('ブラウザ状態取得完了');
        });
    };
    byId('browserOpen').onclick = function(){
        var url = (byId('browserUrl').value || '').trim();
        if (!url) return;
        setStatus('ページを開いています...');
        api('/api/browser/open','POST',{url: url, wait_ms: 1000},function(data){
            renderBrowserOut(data);
            setStatus('ページを開きました');
        });
    };
    byId('browserClick').onclick = function(){
        var sel = (byId('browserSelector').value || '').trim();
        if (!sel) return;
        setStatus('クリック中...');
        api('/api/browser/click','POST',{selector: sel},function(data){
            renderBrowserOut(data);
            setStatus('クリック完了');
        });
    };
    byId('browserWait').onclick = function(){
        setStatus('待機中...');
        api('/api/browser/wait','POST',{ms: 500},function(data){
            renderBrowserOut(data);
            setStatus('待機完了');
        });
    };
    byId('browserType').onclick = function(){
        var sel = (byId('browserSelector').value || '').trim();
        var text = (byId('browserText').value || '').trim();
        var pressEnter = !!byId('browserEnter').checked;
        if (!sel) return;
        setStatus('入力中...');
        api('/api/browser/type','POST',{selector: sel, text: text, press_enter: pressEnter},function(data){
            renderBrowserOut(data);
            setStatus('入力完了');
        });
    };
    byId('browserTextGet').onclick = function(){
        setStatus('テキスト取得中...');
        api('/api/browser/text','GET',null,function(data){
            renderBrowserOut(data);
            setStatus('テキスト取得完了');
        });
    };
    byId('browserShot').onclick = function(){
        setStatus('スクショ取得中...');
        api('/api/browser/screenshot','POST',{full_page: false},function(data){
            renderBrowserOut(data);
            setStatus('スクショ取得完了');
        });
    };

    // Repo index
    byId('indexRepo').onclick = function(){
        var maxFiles = parseInt(byId('indexMaxFiles').value || '500', 10);
        setStatus('索引中...');
        api('/api/index/repo','POST',{max_files: maxFiles},function(data){
            var out = byId('indexOut');
            if (data && data.state){
                out.innerHTML = renderCard('索引実行', renderKV(data.state));
            } else {
                out.innerHTML = '<div class="card">索引を開始しました</div>';
            }
            setStatus('索引完了');
        });
    };
    byId('indexStatus').onclick = function(){
        setStatus('索引状態取得中...');
        api('/api/index/status','GET',null,function(data){
            var out = byId('indexOut');
            out.innerHTML = renderCard('索引状態', renderKV(data || {}));
            setStatus('索引状態取得完了');
        });
    };

    // Quality checks
    byId('qualityRun').onclick = function(){
        setStatus('品質チェック実行中...');
        api('/api/quality/run','POST',null,function(data){
            var out = byId('qualityOut');
            if (data && data.state){
                out.innerHTML = renderCard('品質チェック', renderKV(data.state));
            } else {
                out.innerHTML = '<div class="card">品質チェックを開始しました</div>';
            }
            setStatus('品質チェック完了');
        });
    };
    byId('qualityStatus').onclick = function(){
        setStatus('品質チェック状態取得中...');
        api('/api/quality/status','GET',null,function(data){
            var out = byId('qualityOut');
            out.innerHTML = renderCard('品質チェック状態', renderKV(data || {}));
            setStatus('品質チェック状態取得完了');
        });
    };

    // Code search
    byId('searchBtn').onclick = function(){
        var q = (byId('searchQuery').value || '').trim();
        if (!q) return;
        var maxFiles = parseInt(byId('searchMaxFiles').value || '200', 10);
        var maxMatches = parseInt(byId('searchMaxMatches').value || '50', 10);
        setStatus('検索中...');
        api('/api/code/search','POST',{query: q, max_files: maxFiles, max_matches: maxMatches},function(data){
            var out = byId('searchOut');
            var matches = (data && data.matches) ? data.matches : [];
            if (!matches.length){
                out.innerHTML = '<div class="card">該当なし</div>';
            } else {
                var html = renderCard('検索結果', renderKV({query: data.query || q, files_scanned: data.files_scanned || ''}));
                for (var i=0;i<matches.length;i++){
                    var m = matches[i];
                    html += '<div class="card">'
                        + '<div class="kv">'
                        + '<div>ファイル</div><div>' + escapeHtml(m.file || '') + '</div>'
                        + '<div>行</div><div>' + escapeHtml(String(m.line || '')) + '</div>'
                        + '</div>'
                        + '<div style="margin-top:6px;font-size:12px;">' + escapeHtml(m.text || '') + '</div>'
                        + '</div>';
                }
                out.innerHTML = html;
            }
            setStatus('検索完了');
        });
    };

    // IDE helpers
    byId('ideSearch').onclick = function(){
        var q = (byId('ideQuery').value || '').trim();
        if (!q) return;
        setStatus('検索中...');
        api('/api/code/search','POST',{query: q, max_files: 200, max_matches: 20},function(data){
            var out = byId('ideOut');
            var matches = (data && data.matches) ? data.matches : [];
            if (!matches.length){
                out.innerHTML = '<div class="card">該当なし</div>';
            } else {
                var html = renderCard('検索結果', renderKV({query: data.query || q, files_scanned: data.files_scanned || ''}));
                for (var i=0;i<matches.length;i++){
                    var m = matches[i];
                    html += '<div class="card">'
                        + '<div class="kv">'
                        + '<div>ファイル</div><div>' + escapeHtml(m.file || '') + '</div>'
                        + '<div>行</div><div>' + escapeHtml(String(m.line || '')) + '</div>'
                        + '</div>'
                        + '<div style="margin-top:6px;font-size:12px;">' + escapeHtml(m.text || '') + '</div>'
                        + '</div>';
                }
                out.innerHTML = html;
            }
            setStatus('検索完了');
        });
    };
    byId('ideExplain').onclick = function(){
        var file = (byId('ideFile').value || '').trim();
        if (!file) return;
        var start = parseInt(byId('ideStart').value || '1', 10);
        var end = parseInt(byId('ideEnd').value || '200', 10);
        var question = (byId('ideQuestion').value || '').trim();
        setStatus('説明生成中...');
        api('/api/assist/explain','POST',{file: file, start: start, end: end, question: question},function(data){
            var out = byId('ideOut');
            var answer = (data && data.answer) ? data.answer : '（説明なし）';
            out.innerHTML = renderCard('説明', '<pre>' + escapeHtml(answer) + '</pre>');
            setStatus('説明完了');
        });
    };
    byId('ideSuggest').onclick = function(){
        var file = (byId('ideFile').value || '').trim();
        var instruction = (byId('ideInstruction').value || '').trim();
        if (!file || !instruction) return;
        var start = parseInt(byId('ideStart').value || '1', 10);
        var end = parseInt(byId('ideEnd').value || '200', 10);
        setStatus('提案生成中...');
        api('/api/assist/patch','POST',{file: file, start: start, end: end, instruction: instruction},function(data){
            var out = byId('ideOut');
            var diff = (data && data.diff) ? data.diff : '';
            var html = '';
            if (data && data.error){
                html = renderCard('エラー', '<pre>' + escapeHtml(data.error) + '</pre>');
            } else {
                html = renderCard('差分', '<pre>' + escapeHtml(diff) + '</pre>');
            }
            out.innerHTML = html;
            if (data && data.proposal){
                byId('ideNewCode').value = data.proposal;
            }
            setStatus('提案完了');
        });
    };
    byId('ideApply').onclick = function(){
        var file = (byId('ideFile').value || '').trim();
        var newCode = (byId('ideNewCode').value || '').trim();
        if (!file || !newCode) return;
        var start = parseInt(byId('ideStart').value || '1', 10);
        var end = parseInt(byId('ideEnd').value || '200', 10);
        setStatus('適用中...');
        api('/api/assist/apply','POST',{file: file, start: start, end: end, new_code: newCode},function(data){
            var out = byId('ideOut');
            var ok = data && data.applied ? '成功' : '失敗';
            var html = renderCard('適用結果', renderKV({result: ok, rolled_back: data.rolled_back || false, backup: data.backup || ''}));
            out.innerHTML = html;
            setStatus('適用完了');
        });
    };
    byId('ideDiffSummary').onclick = function(){
        setStatus('差分取得中...');
        var limit = parseInt(byId('ideDiffLimit').value || '20', 10);
        var maxLines = parseInt(byId('ideDiffMaxLines').value || '200', 10);
        var filter = (byId('ideDiffFilter').value || '').trim();
        var sortBy = (byId('ideDiffSort').value || 'time_desc');
        var q = '?limit=' + encodeURIComponent(limit) + '&max_lines=' + encodeURIComponent(maxLines);
        q += '&sort=' + encodeURIComponent(sortBy);
        if (filter) q += '&file_contains=' + encodeURIComponent(filter);
        api('/api/assist/diff_summary' + q,'GET',null,function(data){
            renderDiffSummary(data);
            setStatus('差分取得完了');
        });
    };
    byId('ideHistory').onclick = function(){
        setStatus('履歴取得中...');
        api('/api/assist/history','GET',null,function(data){
            var out = byId('ideOut');
            var items = (data && data.items) ? data.items : [];
            if (!items.length){
                out.innerHTML = '<div class="card">履歴はありません</div>';
            } else {
                var html = '';
                for (var i=0;i<items.length;i++){
                    var it = items[i] || {};
                    html += renderCard('履歴', renderKV({file: it.file || '', applied: it.applied, restored: it.restored, backup: it.backup || ''}));
                }
                out.innerHTML = html;
            }
            setStatus('履歴取得完了');
        });
    };
    byId('ideRestore').onclick = function(){
        var backup = (byId('ideBackup').value || '').trim();
        var file = (byId('ideFile').value || '').trim();
        if (!backup || !file) return;
        setStatus('復元中...');
        api('/api/assist/restore','POST',{backup: backup, file: file},function(data){
            var out = byId('ideOut');
            var ok = data && data.restored ? '成功' : '失敗';
            out.innerHTML = renderCard('復元結果', renderKV({result: ok, file: data.file || '', backup: data.backup || ''}));
            setStatus('復元完了');
        });
    };

    function renderSummary(data){
        var out = byId('summaryOut');
        out.innerHTML = '';
        var list = (data && data.summaries) ? data.summaries : [];
        if (!list.length){ out.innerHTML = '<div class="card">サマリがありません</div>'; return; }
        for (var i=0;i<list.length;i++){
            var s = list[i];
            var card = document.createElement('div');
            card.className = 'card';
            var date = s.date || '----';
            var skills = (s.learned_skills || []).slice(0,3).join(' / ');
            var nd = (s.new_datasets !== undefined && s.new_datasets !== null) ? s.new_datasets : 0;
            var ne = (s.new_examples !== undefined && s.new_examples !== null) ? s.new_examples : 0;
            var ni = (s.new_indexed_documents !== undefined && s.new_indexed_documents !== null) ? s.new_indexed_documents : 0;
            var ap = (s.approved_patches !== undefined && s.approved_patches !== null) ? s.approved_patches : 0;
            var im = (s.index_size_mb !== undefined && s.index_size_mb !== null) ? s.index_size_mb : 0;
            var sc = (s.learned_skills_count !== undefined && s.learned_skills_count !== null) ? s.learned_skills_count : 0;
            card.innerHTML = '<h4>📅 ' + date + '</h4>'
                + '<div class="kv">'
                + '<div>📚 データセット: ' + nd + '</div>'
                + '<div>📊 学習例: ' + ne + '</div>'
                + '<div>🗂️ インデックス: ' + ni + '</div>'
                + '<div>📋 承認パッチ: ' + ap + '</div>'
                + '<div>💾 サイズMB: ' + im + '</div>'
                + '<div>✨ スキル数: ' + sc + '</div>'
                + '</div>'
                + (skills ? '<div style="margin-top:6px;font-size:12px;">✨ ' + skills + '</div>' : '');
            out.appendChild(card);
        }
    }

    function renderDiffSummary(data){
        var out = byId('ideOut');
        out.innerHTML = '';
        var list = (data && data.items) ? data.items : [];
        if (!list.length){ out.innerHTML = '<div class="card">差分がありません</div>'; return; }
        for (var i=0;i<list.length;i++){
            var it = list[i] || {};
            var card = document.createElement('div');
            card.className = 'card';
            if (!it.available){
                card.innerHTML = '<h4>⚠️ 取得不可</h4>'
                    + '<div class="muted">理由: ' + escapeHtml(it.reason || 'unknown') + '</div>';
                out.appendChild(card);
                continue;
            }
            var title = (it.file || 'unknown');
            var ts = it.ts ? new Date(it.ts * 1000).toLocaleString() : '';
            card.innerHTML = '<h4>🧩 ' + escapeHtml(title) + '</h4>'
                + (ts ? '<div class="muted">' + escapeHtml(ts) + '</div>' : '')
                + '<div class="kv" style="margin-top:6px;">'
                + '<div>+追加: ' + (it.added || 0) + '</div>'
                + '<div>-削除: ' + (it.removed || 0) + '</div>'
                + '<div>範囲: ' + (it.start || '-') + '-' + (it.end || '-') + '</div>'
                + '<div>適用: ' + (it.applied ? '✅' : '❌') + '</div>'
                + '</div>'
                + '<div class="log" style="margin-top:6px;"><pre>' + escapeHtml(it.diff || '') + '</pre></div>';
            out.appendChild(card);
        }
    }

    // Patch
    byId('patchList').onclick = function(){
        setStatus('パッチ一覧取得中...');
        api('/api/patch/list','GET',null,function(data){
            renderPatches(data);
            setStatus('パッチ一覧取得完了');
        });
    };
    byId('patchApprove').onclick = function(){
        var patch_id = (byId('patchId').value || '').trim();
        if (!patch_id) return;
        setStatus('パッチ承認中...');
        api('/api/patch/approve','POST',{patch_id: patch_id}, function(data){
            var msg = data.approved ? '✅ ' + patch_id + ' を承認しました' : '❌ ' + patch_id + ' を承認できませんでした';
            byId('patchOut').innerHTML = '<pre>' + escapeHtml(msg) + '</pre>';
            setStatus('パッチ承認完了');
        });
    };

    function renderPatches(data){
        var out = byId('patchOut');
        out.innerHTML = '';
        var list = (data && data.proposals) ? data.proposals : [];
        if (!list.length){ out.innerHTML = '<div class="card">パッチはありません</div>'; return; }
        for (var i=0;i<list.length;i++){
            var p = list[i];
            var card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = '<h4>🧩 ' + escapeHtml(p.id || '') + '</h4>'
                + '<div class="kv">'
                + '<div>📌 ' + escapeHtml(p.title || '') + '</div>'
                + '<div>状態: ' + escapeHtml(p.status || '') + '</div>'
                + '</div>'
                + '<div style="margin-top:6px;font-size:12px;">' + escapeHtml((p.files || []).join(', ')) + '</div>';
            out.appendChild(card);
        }

        // Feature proposals
        byId('featurePropose').onclick = function(){
            var title = (byId('featureTitle').value || '').trim();
            var description = (byId('featureDesc').value || '').trim();
            if (!title || !description) return;
            setStatus('提案作成中...');
            api('/api/feature/propose','POST',{title:title, description:description, requested_by:'manual'}, function(data){
                var out = byId('featureOut');
                if (data.proposal){
                    out.innerHTML = '<pre>' + escapeHtml('✅ 提案を作成しました: ' + data.proposal.id) + '</pre>';
                } else {
                    out.innerHTML = '<pre>❌ 提案作成に失敗しました</pre>';
                }
                setStatus('提案作成完了');
            });
        };

        byId('featureList').onclick = function(){
            setStatus('提案一覧取得中...');
            api('/api/feature/list','GET',null,function(data){
                var out = byId('featureOut');
                var list = (data && data.proposals) ? data.proposals : [];
                if (!list.length){
                    out.innerHTML = '<div class="card">提案はありません</div>';
                } else {
                    var html = '';
                    for (var i=0;i<list.length;i++){
                        var p = list[i];
                        html += '<div class="card">'
                            + '<h4>🧩 ' + escapeHtml(p.id || '') + '</h4>'
                            + '<div class="kv">'
                            + '<div>📌 ' + escapeHtml(p.title || '') + '</div>'
                            + '<div>状態: ' + escapeHtml(p.status || '') + '</div>'
                            + '</div>'
                            + '<div style="margin-top:6px;font-size:12px;">' + escapeHtml(p.description || '') + '</div>'
                            + '</div>';
                    }
                    out.innerHTML = html;
                }
                setStatus('提案一覧取得完了');
            });
        };

        byId('featureApprove').onclick = function(){
            var proposal_id = (byId('featureId').value || '').trim();
            if (!proposal_id) return;
            setStatus('提案承認中...');
            api('/api/feature/approve','POST',{proposal_id: proposal_id}, function(data){
                var msg = data.approved ? '✅ 承認しました' : '❌ 承認できませんでした';
                byId('featureOut').innerHTML = '<pre>' + escapeHtml(msg) + '</pre>';
                setStatus('提案承認完了');
            });
        };
    }

    // Logs
    byId('logTail').onclick = function(){
        var lines = parseInt(byId('logLines').value || '30', 10);
        var filter = (byId('logFilter').value || '').trim();
        setStatus('ログ取得中...');
        api('/api/logs/tail','POST',{lines: lines, filter: filter}, function(data){
            var out = byId('logOut');
            if (!data.lines || data.lines.length === 0){
                out.innerHTML = '<div class="card">ログがありません</div>';
            } else {
                out.innerHTML = '<pre>' + escapeHtml(data.lines.join('\\n')) + '</pre>';
            }
            setStatus('ログ取得完了');
        });
    };

    byId('logSearchBtn').onclick = function(){
        var search = (byId('logSearch').value || '').trim();
        if (!search) return;
        setStatus('ログ検索中...');
        api('/api/logs/search','POST',{search: search}, function(data){
            var out = byId('logOut');
            if (!data.matches || data.matches.length === 0){
                out.innerHTML = '<div class="card">該当なし</div>';
            } else {
                var chunks = [];
                for (var i=0;i<data.matches.length;i++){
                    var m = data.matches[i];
                    chunks.push('#' + m.line + '\\n' + (m.context || []).join('\\n'));
                }
                out.innerHTML = '<pre>' + escapeHtml(chunks.join('\\n\\n---\\n\\n')) + '</pre>';
            }
            setStatus('ログ検索完了');
        });
    };

    // Dashboard
    byId('dashOpen').onclick = function(){
        setStatus('ダッシュボード取得中...');
        api('/api/dashboard/html','GET',null,function(data){
            var out = byId('dashOut');
            if (data.html){
                out.innerHTML = '<iframe style="width:100%;height:60vh;border:1px solid #1c2438;border-radius:10px;background:#0f1629" srcdoc="' + String(data.html).replace(/"/g,'&quot;') + '"></iframe>';
            } else {
                out.innerHTML = '<div class="card">取得できませんでした</div>';
            }
            setStatus('ダッシュボード表示完了');
        });
    };


    function formatIdle(data){
        if (!data) return '（結果なし）';
        var payload = data.result || data.status || data;
        if (!payload) return '（結果なし）';

        if (typeof payload === 'string') {
            return idleStatusMessage(payload);
        }
        if (payload.status) {
            return idleStatusMessage(payload.status) + formatIdleDetails(payload);
        }
        return JSON.stringify(payload, null, 2);
    }

    function idleStatusMessage(status){
        if (status === 'already_running') return '✅ 放置モードはすでに実行中です。';
        if (status === 'started') return '✅ 放置モードを開始しました。';
        if (status === 'stopped') return '✅ 放置モードを停止しました。';
        if (status === 'running') return '✅ 放置モードは稼働中です。';
        if (status === 'not_running') return 'ℹ️ 放置モードは未起動です。';
        if (status === 'crashed') return '❌ 放置モードが起動後に停止しました。';
        if (status === 'error') return '❌ 放置モードの操作に失敗しました。';
        return 'ℹ️ 放置モード状態: ' + status;
    }

    function formatIdleDetails(payload){
        var extra = '';
        if (payload.pids) extra += '\\nPIDs: ' + JSON.stringify(payload.pids);
        if (payload.alive_pids) extra += '\\nAlive: ' + JSON.stringify(payload.alive_pids);
        if (payload.reason) extra += '\\n理由: ' + payload.reason;
        if (payload.idle !== undefined) extra += '\\n稼働中: ' + payload.idle;
        return extra;
    }
})();
</script>
</body>
</html>
""", headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})


@app.post("/api/generate/code")
async def generate_code(req: CodeRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    code = assistant.generate_code(req.requirement, req.language)
    return {"code": code}


@app.post("/api/generate/ui")
async def generate_ui(req: UIRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    html = assistant.generate_ui(req.description)
    return {"html": html}


@app.post("/api/generate/3d")
async def generate_3d(req: Model3DRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    model = assistant.generate_3d_model(req.description)
    return {"scene": model}


@app.post("/api/generate/summary")
async def generate_summary(req: TextRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    summary = assistant.summarize_text(req.text)
    return {"summary": summary}


@app.post("/api/generate/plan")
async def generate_plan(req: PlanRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    plan = assistant.generate_plan(req.requirement)
    return {"plan": plan}


@app.post("/api/idle/start")
async def idle_start(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    idle = IdleMode()
    return {"result": idle.start_idle()}


@app.post("/api/idle/stop")
async def idle_stop(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    idle = IdleMode()
    return {"result": idle.stop_idle()}


@app.get("/api/idle/status")
async def idle_status(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    idle = IdleMode()
    return {"status": idle.status()}


@app.post("/api/idle/restart")
async def idle_restart(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    idle = IdleMode()
    idle.stop_idle()
    return {"result": idle.start_idle()}


@app.get("/api/status")
async def system_status(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    idle = IdleMode()
    dash = IdleModeDashboard()
    return {
        "idle": idle.status(),
        "worker": dash.get_worker_status(),
        "monitor": dash.get_monitor_status(),
        "uptime": dash.get_system_uptime(),
        "learning": dash.get_learning_stats(),
        "vector_store": dash.get_vector_store_stats()
    }


@app.get("/api/health")
async def system_health(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    dash = IdleModeDashboard()
    return dash.get_health()


@app.post("/api/heal")
async def system_heal(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    dash = IdleModeDashboard()
    before = dash.get_health()
    healed = False
    action = 'noop'
    if not before.get('ok'):
        idle = IdleMode()
        idle.stop_idle()
        idle.start_idle()
        healed = True
        action = 'restart_idle'
    after = dash.get_health()
    return {"healed": healed, "action": action, "before": before, "after": after}


@app.post("/api/summary/daily")
async def summary_daily(req: SummaryRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    summaries = load_recent_summaries(days=req.days)
    return {"summaries": summaries}


@app.get("/api/summary/all")
async def summary_all(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    # reuse daily loader for all summaries
    summaries = load_recent_summaries(days=36500)
    return {"summaries": summaries}


@app.get("/api/patch/list")
async def patch_list(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"proposals": PatchValidator.list_proposals()}


@app.post("/api/patch/approve")
async def patch_approve(req: PatchApproveRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    ok = PatchValidator.approve_proposal(req.patch_id)
    return {"approved": ok}


@app.post("/api/logs/tail")
async def logs_tail(req: LogRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    monitor = LiveMonitor()
    log_file = monitor.log_file
    if not log_file.exists():
        return {"lines": []}
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-req.lines:]
    if req.filter:
        lines = monitor.filter_logs(lines, req.filter)
    return {"lines": [l.rstrip() for l in lines]}


@app.post("/api/logs/search")
async def logs_search(req: LogRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    monitor = LiveMonitor()
    log_file = monitor.log_file
    if not log_file.exists():
        return {"matches": []}
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    matches = []
    for i, line in enumerate(lines):
        if req.search.lower() in line.lower():
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            matches.append({
                "line": i + 1,
                "context": [lines[j].rstrip() for j in range(start, end)]
            })
    return {"matches": matches}


@app.get("/api/dashboard/html")
async def dashboard_html(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    dash = IdleModeDashboard()
    return {"html": dash.get_html_dashboard()}


@app.get("/api/dashboard/data")
async def dashboard_data(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    dash = IdleModeDashboard()
    return dash.get_dashboard_data()


@app.get("/api/feature/list")
async def feature_list(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"proposals": list_feature_proposals()}


@app.post("/api/feature/propose")
async def feature_propose(req: FeatureProposalRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    proposal = create_feature_proposal(req.title, req.description, req.requested_by)
    return {"proposal": proposal}


@app.post("/api/feature/approve")
async def feature_approve(req: FeatureApproveRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    ok = approve_feature_proposal(req.proposal_id)
    return {"approved": ok}


@app.get("/api/rss/list")
async def rss_list(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"sources": rss_load_sources()}


@app.post("/api/rss/add")
async def rss_add(req: RssSourceRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"sources": rss_add_source(req.url)}


@app.post("/api/rss/remove")
async def rss_remove(req: RssSourceRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"sources": rss_remove_source(req.url)}


@app.post("/api/rss/collect")
async def rss_collect_api(req: RssCollectRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    sources = rss_load_sources()
    max_items = req.max_items or Config.RSS_MAX_ITEMS
    urls = rss_collect(sources, max_items=max_items)
    # append to watchlist
    try:
        existing = []
        if Config.WATCHLIST_FILE.exists():
            existing = [l.strip() for l in Config.WATCHLIST_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
        merged = existing[:]
        added = 0
        for u in urls:
            if u not in merged:
                merged.append(u)
                added += 1
        if added:
            Config.WATCHLIST_FILE.write_text("\n".join(merged) + "\n", encoding="utf-8")
    except Exception:
        added = 0
    return {"sources": sources, "added": added, "count": len(urls)}


@app.post("/api/local/ingest")
async def local_ingest_api(req: LocalIngestRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    if local_ingest_state["running"]:
        return {"started": False, "reason": "already_running", "state": local_ingest_state}

    def _run_local_ingest():
        local_ingest_state["running"] = True
        local_ingest_state["last_error"] = None
        local_ingest_state["updated_at"] = int(time.time())
        try:
            ingest_result = ingest_local_docs_to_clean(force=req.force)
            result = {"ingest": ingest_result}
            if req.rebuild:
                result["vector_store"] = build_vector_store_from_clean()
            local_ingest_state["last_result"] = result
        except Exception as e:
            local_ingest_state["last_error"] = str(e)
        finally:
            local_ingest_state["running"] = False
            local_ingest_state["updated_at"] = int(time.time())

    t = threading.Thread(target=_run_local_ingest, daemon=True)
    t.start()
    return {"started": True, "state": local_ingest_state}


@app.post("/api/ocr/upload")
async def ocr_upload_api(
    file: UploadFile = File(...),
    learn: bool = Form(True),
    rebuild: bool = Form(True),
    x_api_key: str = Header(default=None),
):
    _check_token(x_api_key)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file")
    uploads_dir = Config.DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename).suffix or ".png"
    safe_name = f"upload_{int(time.time())}{suffix}"
    out_path = uploads_dir / safe_name
    content = await file.read()
    out_path.write_bytes(content)

    if not learn:
        text = process_image_for_learning(out_path, rebuild=False).get("text", "")
        return {"ok": True, "text": text, "file": str(out_path)}

    result = process_image_for_learning(out_path, rebuild=rebuild)
    result.update({"file": str(out_path)})
    return result


@app.post("/api/ocr/watch/start")
async def ocr_watch_start_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    global _ocr_watch_thread
    if ocr_watch_state["running"]:
        return {"started": False, "state": ocr_watch_state}

    ocr_watch_state["running"] = True
    ocr_watch_state["last_error"] = None
    ocr_watch_state["updated_at"] = int(time.time())

    def _loop():
        while ocr_watch_state.get("running"):
            try:
                res = ingest_images_from_dirs(Config.OCR_WATCH_DIRS, rebuild=False)
                ocr_watch_state["last_result"] = res
            except Exception as e:
                ocr_watch_state["last_error"] = str(e)
            ocr_watch_state["updated_at"] = int(time.time())
            time.sleep(max(5, int(Config.OCR_WATCH_INTERVAL_SECONDS or 60)))

    _ocr_watch_thread = threading.Thread(target=_loop, daemon=True)
    _ocr_watch_thread.start()
    return {"started": True, "state": ocr_watch_state}


@app.post("/api/ocr/watch/stop")
async def ocr_watch_stop_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    ocr_watch_state["running"] = False
    ocr_watch_state["updated_at"] = int(time.time())
    return {"stopped": True, "state": ocr_watch_state}


@app.get("/api/ocr/watch/status")
async def ocr_watch_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"state": ocr_watch_state, "dirs": [str(p) for p in Config.OCR_WATCH_DIRS]}


@app.get("/api/local/status")
async def local_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {
        "state": local_ingest_state,
        "last_state": load_local_docs_state(),
        "ocr": {
            "enabled": bool(getattr(Config, "OCR_ENABLED", False)),
            "lang": getattr(Config, "OCR_LANG", "eng"),
            "image_exts": getattr(Config, "OCR_IMAGE_EXTS", []),
            "max_pixels": getattr(Config, "OCR_MAX_PIXELS", None),
        },
        "local_docs": {
            "dirs": [str(p) for p in (Config.LOCAL_DOC_DIRS or [])],
            "exts": Config.LOCAL_DOC_EXTS,
            "cooldown_seconds": Config.LOCAL_DOC_INGEST_MIN_INTERVAL_SECONDS,
            "max_files": Config.LOCAL_DOC_MAX_FILES,
            "max_chars": Config.LOCAL_DOC_MAX_CHARS,
        },
    }


@app.post("/api/browser/start")
async def browser_start_api(req: BrowserStartRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        browser_state["running"] = True
        browser_state["last_error"] = None
        browser_state["updated_at"] = int(time.time())
        browser.open("about:blank", wait_ms=0, headless=req.headless)
        browser_state["current_url"] = "about:blank"
        browser_state["current_title"] = ""
        return {"started": True, "state": browser_state}
    except Exception as e:
        browser_state["running"] = False
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"started": False, "error": str(e), "state": browser_state}


@app.post("/api/browser/stop")
async def browser_stop_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        browser.stop()
        browser_state["running"] = False
        browser_state["updated_at"] = int(time.time())
        return {"stopped": True, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"stopped": False, "error": str(e), "state": browser_state}


@app.get("/api/browser/status")
async def browser_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"state": browser_state}


@app.post("/api/browser/open")
async def browser_open_api(req: BrowserOpenRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    if not is_http_url(req.url):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        info = browser.open(req.url, wait_ms=req.wait_ms)
        browser_state["running"] = True
        browser_state["current_url"] = info.url
        browser_state["current_title"] = info.title
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "info": info.__dict__, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.post("/api/browser/click")
async def browser_click_api(req: BrowserClickRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        browser.click(req.selector)
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.post("/api/browser/type")
async def browser_type_api(req: BrowserTypeRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        browser.type_text(req.selector, req.text, press_enter=req.press_enter)
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.post("/api/browser/wait")
async def browser_wait_api(req: BrowserWaitRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        browser.wait(req.ms)
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.get("/api/browser/text")
async def browser_text_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        text = browser.get_text()
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "text": text, "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.post("/api/browser/screenshot")
async def browser_screenshot_api(req: BrowserScreenshotRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    try:
        path = browser.screenshot(full_page=req.full_page)
        browser_state["updated_at"] = int(time.time())
        return {"ok": True, "path": str(path), "state": browser_state}
    except Exception as e:
        browser_state["last_error"] = str(e)
        browser_state["updated_at"] = int(time.time())
        return {"ok": False, "error": str(e), "state": browser_state}


@app.get("/api/providers/status")
async def providers_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {
        "llm": get_provider_status("llm", "ollama"),
        "ocr": get_provider_status("ocr", "tesseract"),
    }


@app.post("/api/providers/score")
async def providers_score_api(req: ProviderScoreRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return record_provider_score(req.kind, req.provider, req.score, req.notes)


@app.post("/api/index/repo")
async def index_repo_api(req: IndexRepoRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    if index_state["running"]:
        return {"started": False, "reason": "already_running", "state": index_state}

    def _run_index():
        index_state["running"] = True
        index_state["last_error"] = None
        index_state["updated_at"] = int(time.time())
        try:
            result = index_repository(max_files=req.max_files, exts=req.exts)
            index_state["last_result"] = result
        except Exception as e:
            index_state["last_error"] = str(e)
        finally:
            index_state["running"] = False
            index_state["updated_at"] = int(time.time())

    t = threading.Thread(target=_run_index, daemon=True)
    t.start()
    return {"started": True, "state": index_state}


@app.get("/api/index/status")
async def index_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return index_state


@app.post("/api/quality/run")
async def quality_run_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    if quality_state["running"]:
        return {"started": False, "reason": "already_running", "state": quality_state}

    def _run_quality():
        quality_state["running"] = True
        quality_state["last_error"] = None
        quality_state["updated_at"] = int(time.time())
        try:
            result = run_quality_checks()
            quality_state["last_result"] = result
        except Exception as e:
            quality_state["last_error"] = str(e)
        finally:
            quality_state["running"] = False
            quality_state["updated_at"] = int(time.time())

    t = threading.Thread(target=_run_quality, daemon=True)
    t.start()
    return {"started": True, "state": quality_state}


@app.get("/api/quality/status")
async def quality_status_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return quality_state


@app.post("/api/code/search")
async def code_search_api(req: CodeSearchRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    max_files = req.max_files or Config.SEARCH_MAX_FILES
    max_matches = req.max_matches or Config.SEARCH_MAX_MATCHES
    result = search_code(req.query, max_files=max_files, max_matches=max_matches)
    return result


@app.post("/api/assist/explain")
async def assist_explain_api(req: ExplainRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    target = _safe_path(req.file)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    start = max(1, int(req.start))
    end = max(start, int(req.end))
    text = target.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    snippet = "\n".join(lines[start - 1:end])
    question = req.question.strip() if req.question else ""
    prompt = (
        "以下のコードの内容を日本語で簡潔に説明してください。"
        "重要な意図、入力/出力、注意点があれば述べてください。\n\n"
        f"ファイル: {req.file}\n"
        f"範囲: {start}-{end}\n\n"
        f"コード:\n{snippet}\n\n"
        + (f"追加の質問: {question}\n\n" if question else "")
        + "説明:"
    )
    answer = assistant.llm.generate(prompt, temperature=0.2, max_tokens=400)
    return {"file": req.file, "start": start, "end": end, "answer": answer}


@app.post("/api/assist/patch")
async def assist_patch_api(req: PatchPreviewRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    target = _safe_path(req.file)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    start = max(1, int(req.start))
    end = max(start, int(req.end))
    text = target.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    snippet = "\n".join(lines[start - 1:end])
    prompt = (
        "以下のコードの一部を変更します。指示に従って、指定範囲の新しいコードのみを返してください。"
        "前後の説明やコードブロックは不要です。\n\n"
        f"ファイル: {req.file}\n"
        f"範囲: {start}-{end}\n\n"
        f"現在のコード:\n{snippet}\n\n"
        f"指示:\n{req.instruction}\n\n"
        "新しいコード:"
    )
    new_code = assistant.llm.generate(prompt, temperature=0.2, max_tokens=600)
    if new_code.startswith("エラー:"):
        return {"file": req.file, "start": start, "end": end, "error": new_code}

    try:
        import difflib
        old_lines = snippet.splitlines()
        new_lines = new_code.splitlines()
        diff = "\n".join(difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after", lineterm=""))
    except Exception as e:
        diff = f"diff生成失敗: {e}"

    return {
        "file": req.file,
        "start": start,
        "end": end,
        "proposal": new_code,
        "diff": diff
    }


@app.post("/api/assist/apply")
async def assist_apply_api(req: ApplyRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    target = _safe_path(req.file)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    start = max(1, int(req.start))
    end = max(start, int(req.end))
    text = target.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if start > len(lines):
        raise HTTPException(status_code=400, detail="Start line out of range")
    if end > len(lines):
        end = len(lines)
    backup_path = _backup_file(target)
    new_lines = req.new_code.splitlines()
    updated = lines[:start - 1] + new_lines + lines[end:]
    target.write_text("\n".join(updated) + "\n", encoding="utf-8")
    # run quality checks and rollback on failure
    qc = run_quality_checks()
    if not qc.get("ok"):
        try:
            shutil.copy2(backup_path, target)
        except Exception as e:
            add_apply_record({
                "file": req.file,
                "start": start,
                "end": end,
                "applied": False,
                "rolled_back": False,
                "error": str(e),
                "backup": str(backup_path),
            })
            return {"applied": False, "rolled_back": False, "error": str(e), "quality": qc}
        add_apply_record({
            "file": req.file,
            "start": start,
            "end": end,
            "applied": False,
            "rolled_back": True,
            "backup": str(backup_path),
        })
        return {"applied": False, "rolled_back": True, "quality": qc}
    add_apply_record({
        "file": req.file,
        "start": start,
        "end": end,
        "applied": True,
        "backup": str(backup_path),
    })
    return {
        "applied": True,
        "file": req.file,
        "start": start,
        "end": end,
        "new_lines": len(new_lines),
        "quality": qc,
        "backup": str(backup_path)
    }


@app.get("/api/assist/history")
async def assist_history_api(x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    return {"items": list_apply_records(50)}


@app.get("/api/assist/diff_summary")
async def assist_diff_summary_api(limit: int = 20, max_lines: int = 200, file_contains: str = "", sort: str = "time_desc", x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    items = list_apply_records(limit)
    summaries = []
    for item in items:
        if file_contains:
            file_path = str(item.get("file") or "")
            if file_contains not in file_path:
                continue
        summaries.append(_build_diff_summary_item(item, max_lines=max_lines))
    if sort == "impact_desc":
        def _impact(s):
            if not s.get("available"):
                return -1
            return int(s.get("added") or 0) + int(s.get("removed") or 0)
        summaries = sorted(summaries, key=_impact, reverse=True)
    else:
        summaries = sorted(summaries, key=lambda s: int(s.get("ts") or 0), reverse=True)
    return {"items": summaries}


@app.post("/api/assist/restore")
async def assist_restore_api(req: RestoreRequest, x_api_key: str = Header(default=None)):
    _check_token(x_api_key)
    target = _safe_path(req.file)
    backup = _safe_path(req.backup)
    if not backup.exists() or not backup.is_file():
        raise HTTPException(status_code=404, detail="Backup not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Target not found")
    shutil.copy2(backup, target)
    add_apply_record({
        "file": req.file,
        "restored_from": req.backup,
        "applied": False,
        "restored": True,
    })
    return {"restored": True, "file": req.file, "backup": req.backup}

if __name__ == '__main__':
    import uvicorn
    reload_enabled = os.getenv("AI_ASSISTANT_API_RELOAD", "1") == "1"
    if reload_enabled:
        uvicorn.run("api:app", host=Config.API_HOST, port=Config.API_PORT, reload=True)
    else:
        uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)
