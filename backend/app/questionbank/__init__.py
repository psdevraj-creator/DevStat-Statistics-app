"""DevStat question banks — purchasable MCQ packs (100 questions + synthetic data).

Each bank is a JSON file in this directory with its own dataset (loaded via the
router). Banks cost £5 and are available only to subscribed (licensed) users.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).resolve().parent


def _load() -> Dict[str, dict]:
    packs: Dict[str, dict] = {}
    for f in _DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("id") and isinstance(d.get("questions"), list):
                packs[d["id"]] = d
        except Exception:
            continue
    return packs


PACKS: Dict[str, dict] = _load()


def list_packs() -> List[Dict[str, Any]]:
    return [{
        "id": p["id"], "title": p["title"], "blurb": p["blurb"], "emoji": p["emoji"],
        "price_cents": p["price_cents"], "free": p["price_cents"] == 0,
        "questions": len(p["questions"]),
    } for p in PACKS.values()]


def get_pack(sid: str) -> Optional[Dict[str, Any]]:
    return PACKS.get(sid)
