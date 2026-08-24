"""Dataset Scanner — introspects the current DevStat dataset and builds a data dictionary."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import app.state as _state

logger = logging.getLogger("devstat.ai.scanner")


def _safe_val(v: Any) -> Any:
    """Convert non-serializable types to native Python."""
    if v is None:
        return None
    if hasattr(v, "item"):
        return v.item()
    if hasattr(v, "dtype"):
        return v.tolist() if hasattr(v, "tolist") else str(v)
    return v


COLUMN_TYPE_MAP = {
    "numeric": "continuous",
    "scale": "continuous",
    "continuous": "continuous",
    "ordinal": "ordinal",
    "nominal": "categorical",
    "categorical": "categorical",
    "binary": "binary",
    "string": "categorical",
    "text": "categorical",
    "date": "datetime",
    "survival_time": "survival_time",
    "event_indicator": "event_indicator",
}


def _normalize_type(raw_type: str, unique_count: int, is_numeric: bool) -> str:
    rt = raw_type.lower().strip()
    if unique_count == 2 and not is_numeric:
        return "binary"
    if rt in ("binary", "binomial"):
        return "binary"
    if rt in COLUMN_TYPE_MAP:
        return COLUMN_TYPE_MAP[rt]
    if not is_numeric:
        return "categorical"
    if unique_count <= 10:
        return "ordinal"
    return "continuous"


def build_data_dictionary() -> List[Dict[str, Any]]:
    """Build data dictionary from the currently loaded dataset."""
    df = _state.current_data
    if df is None:
        return []

    dictionary = []
    for col_name in df.columns:
        series = df[col_name]
        clean = series.dropna()
        n_unique = int(clean.nunique()) if len(clean) > 0 else 0
        is_num = series.dtype.kind in ("i", "f", "u")
        missing = int(series.isna().sum())

        meta = _state.variable_metadata.get(col_name, {})
        raw_type = meta.get("measure", "scale" if is_num else "nominal")
        inferred = _normalize_type(raw_type, n_unique, is_num)

        unique_vals = clean.unique()[:10] if len(clean) > 0 else []
        entry = {
            "name": col_name,
            "type": inferred,
            "dtype": str(series.dtype),
            "unique_count": n_unique,
            "missing_count": missing,
            "missing_pct": round(missing / len(df) * 100, 1) if len(df) > 0 else 0.0,
            "values": [_safe_val(v) for v in unique_vals],
        }
        dictionary.append(entry)
    return dictionary


def format_data_dictionary(dictionary: Optional[List[Dict[str, Any]]] = None) -> str:
    """Format the data dictionary as a readable string for LLM prompts."""
    if dictionary is None:
        dictionary = build_data_dictionary()
    if not dictionary:
        return "No dataset loaded."

    lines = ["Available variables in the loaded dataset:\n"]
    for col in dictionary:
        parts = [
            f"  - {col['name']}: {col['type']}",
            f"(dtype={col['dtype']}, {col['unique_count']} unique",
        ]
        if col["missing_count"]:
            parts.append(f"{col['missing_pct']:.0f}% missing")
        parts.append(")")
        if col.get("values") and len(col["values"]) <= 10:
            parts.append(f"values: {col['values']}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def scan_dataset() -> Optional[Dict[str, Any]]:
    """Return enriched dataset info for the AI router."""
    if _state.current_data is None:
        return None

    try:
        dict_ = build_data_dictionary()
        return {
            "name": _state.current_filename or "untitled",
            "rows": len(_state.current_data),
            "cols": len(_state.current_data.columns),
            "columns": dict_,
            "formatted": format_data_dictionary(dict_),
        }
    except Exception as e:
        logger.exception("scan_dataset failed: %s", e)
        return {
            "name": _state.current_filename or "untitled",
            "rows": len(_state.current_data),
            "cols": len(_state.current_data.columns),
            "columns": [],
            "formatted": f"Error scanning dataset: {e}",
            "error": str(e),
        }
