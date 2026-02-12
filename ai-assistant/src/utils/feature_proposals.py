import json
from pathlib import Path
from datetime import datetime
from config import Config

PROPOSALS_FILE = Config.DATA_DIR / "feature_proposals.json"


def _load():
    if PROPOSALS_FILE.exists():
        try:
            return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(items):
    PROPOSALS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_proposals(status=None):
    items = _load()
    if status:
        items = [p for p in items if p.get("status") == status]
    return items


def create_proposal(title: str, description: str, requested_by: str = "auto"):
    items = _load()
    pid = datetime.now().strftime("%Y%m%d_%H%M%S")
    proposal = {
        "id": pid,
        "title": title,
        "description": description,
        "status": "PROPOSED",
        "requested_by": requested_by,
        "created_at": datetime.now().isoformat(),
    }
    items.append(proposal)
    _save(items)
    return proposal


def approve_proposal(pid: str):
    items = _load()
    for p in items:
        if p.get("id") == pid:
            if p.get("status") != "PROPOSED":
                return False
            p["status"] = "APPROVED"
            p["approved_at"] = datetime.now().isoformat()
            _save(items)
            return True
    return False
