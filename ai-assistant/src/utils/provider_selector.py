"""
Provider selector for auto-replacement when internal implementations reach parity.
"""
import json
import logging
from typing import Dict, Any, Optional

from config import Config

logger = logging.getLogger(__name__)


def _load_scores() -> Dict[str, Dict[str, Any]]:
    try:
        if Config.PROVIDER_SCORES_FILE.exists():
            data = json.loads(Config.PROVIDER_SCORES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"[PROVIDER] Failed to load scores: {e}")
    return {}


def _save_scores(scores: Dict[str, Dict[str, Any]]):
    try:
        Config.PROVIDER_SCORES_FILE.write_text(
            json.dumps(scores, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[PROVIDER] Failed to save scores: {e}")


def record_provider_score(kind: str, provider: str, score: float, notes: str = "") -> Dict[str, Any]:
    scores = _load_scores()
    k = (kind or "").strip().lower()
    p = (provider or "").strip().lower()
    if not k or not p:
        return {"ok": False, "reason": "kind_or_provider_missing"}
    scores.setdefault(k, {})[p] = {
        "score": float(score),
        "notes": notes or "",
    }
    _save_scores(scores)
    return {"ok": True, "scores": scores.get(k, {})}


def select_provider(kind: str, fallback: str) -> str:
    k = (kind or "").strip().lower()
    policy = (Config.PROVIDER_POLICY or {}).get(k, {})
    preferred = (policy.get("preferred") or fallback or "").strip().lower()
    min_score = float(policy.get("min_score", 0) or 0)
    auto_switch = bool(policy.get("auto_switch", False))

    if not auto_switch:
        return preferred or fallback

    scores = _load_scores().get(k, {})
    best_provider: Optional[str] = None
    best_score = min_score
    for provider, info in scores.items():
        try:
            s = float(info.get("score", 0))
        except Exception:
            s = 0.0
        if s >= best_score:
            best_score = s
            best_provider = provider
    return best_provider or preferred or fallback


def get_provider_status(kind: str, fallback: str) -> Dict[str, Any]:
    k = (kind or "").strip().lower()
    policy = (Config.PROVIDER_POLICY or {}).get(k, {})
    selected = select_provider(k, fallback)
    scores = _load_scores().get(k, {})
    return {
        "kind": k,
        "selected": selected,
        "policy": policy,
        "scores": scores,
    }
