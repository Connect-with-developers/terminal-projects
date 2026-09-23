"""Auto-generated project file."""
from __future__ import annotations

"""Simple JSON store."""
import json, os
DB = os.path.join(os.path.dirname(__file__), "db.json")
def load() -> dict:
    """Load data, return {} if missing."""
    try:
        return json.load(open(DB))
    except Exception:
        return {}
def save(data: dict) -> None:
    """Save data."""
    json.dump(data, open(DB, "w"), indent=2)
