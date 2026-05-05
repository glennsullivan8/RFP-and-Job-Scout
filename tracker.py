"""
tracker.py  —  Persistent opportunity tracker
Stores status of every opportunity seen: new / saved / applied / hidden
Uses a local JSON file (committed to repo) as the database.
"""

import json
import os
from datetime import datetime
from pathlib import Path

TRACKER_FILE = Path(os.getenv("TRACKER_FILE", "data/tracker.json"))

STATUSES = {
    "new":         "Never seen before",
    "seen":        "Appeared in digest, no action taken",
    "saved":       "Flagged for later review",
    "applied":     "Application submitted",
    "generating":  "Application doc being generated",
    "hidden":      "Not interested — permanently hidden",
}


def _load() -> dict:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TRACKER_FILE.exists():
        try:
            return json.loads(TRACKER_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save(data: dict) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_FILE.write_text(json.dumps(data, indent=2, default=str))


def get_status(opp_id: str) -> str:
    data = _load()
    return data.get(opp_id, {}).get("status", "new")


def set_status(opp_id: str, status: str, meta: dict = None) -> None:
    assert status in STATUSES, f"Unknown status: {status}"
    data = _load()
    entry = data.get(opp_id, {})
    entry["status"] = status
    entry["updated"] = datetime.utcnow().isoformat()
    if meta:
        entry.update(meta)
    data[opp_id] = entry
    _save(data)


def mark_seen(opp_id: str, title: str, source: str, opp_type: str) -> None:
    data = _load()
    if opp_id not in data:
        data[opp_id] = {
            "status": "seen",
            "title": title[:80],
            "source": source,
            "type": opp_type,
            "first_seen": datetime.utcnow().isoformat(),
            "updated": datetime.utcnow().isoformat(),
        }
        _save(data)


def is_hidden(opp_id: str) -> bool:
    return get_status(opp_id) == "hidden"


def mark_applied(opp_id: str, doc_path: str = "") -> None:
    set_status(opp_id, "applied", {
        "applied_date": datetime.utcnow().isoformat(),
        "doc_path": doc_path,
    })


def mark_hidden(opp_id: str) -> None:
    set_status(opp_id, "hidden")


def get_applied_count() -> int:
    return sum(1 for v in _load().values() if v.get("status") == "applied")


def get_all_records() -> dict:
    return _load()


def filter_opportunities(opps: list[dict]) -> list[dict]:
    """Remove any opportunities already marked as hidden."""
    return [o for o in opps if not is_hidden(o.get("id", ""))]


def mark_all_seen(opps: list[dict], opp_type: str) -> None:
    """Record first-seen for every opportunity in a list."""
    for o in opps:
        mark_seen(o["id"], o.get("title", ""), o.get("source", ""), opp_type)
