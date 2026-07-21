"""
DevStat global application state.

Holds the in-memory dataset, filename, variable metadata, and undo history.
All routers share this module to access and modify the current state.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def require_data() -> None:
    """Raise ``400`` if no dataset is currently loaded."""
    if current_data is None:
        raise HTTPException(
            status_code=400,
            detail="No dataset is currently loaded. Upload a file first.",
        )


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

current_data: Optional[pd.DataFrame] = None
current_filename: str = ""

# Variable metadata — dict keyed by column name
#   name: str          — variable name
#   type: str          — numeric, string, date, comma, dot, dollar, etc.
#   width: int         — display width
#   decimals: int      — decimal places
#   label: str         — variable label (descriptive text)
#   value_labels: dict — e.g. {1: "Male", 2: "Female"}
#   missing_values: list — user-defined missing values
#   columns: int       — column width in data view
#   align: str         — left, center, right
#   measure: str       — scale, ordinal, nominal
#   role: str          — input, target, both, none, partition, split
variable_metadata: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Undo / Redo stack
# ---------------------------------------------------------------------------

@dataclass
class EditAction:
    """A single reversible data edit."""
    description: str  # human-readable, e.g. "Edit cell [0, 'age']"
    # Snapshot of the entire DataFrame before the edit
    df_snapshot: Optional[str] = None       # CSV serialised snapshot
    meta_snapshot: Optional[str] = None      # JSON serialised metadata snapshot
    # For lightweight edits, store before/after values
    edit_type: str = ""   # "cell", "row_insert", "row_delete", "col_add", "col_delete", "batch"
    edit_detail: Dict[str, Any] = field(default_factory=dict)


_MAX_UNDO = 100
_undo_stack: List[EditAction] = []
_redo_stack: List[EditAction] = []


def _snapshot_df() -> str:
    """Serialise the current DataFrame to CSV for undo."""
    if current_data is None:
        return ""
    return current_data.to_csv(index=False)


def _snapshot_meta() -> str:
    """Serialise variable metadata to JSON for undo."""
    import json
    return json.dumps(variable_metadata, default=str)


def _restore_df(csv_str: str) -> None:
    """Restore DataFrame from a CSV snapshot."""
    global current_data
    if csv_str:
        from io import StringIO
        current_data = pd.read_csv(StringIO(csv_str))
    else:
        current_data = None


def _restore_meta(json_str: str) -> None:
    """Restore variable metadata from a JSON snapshot."""
    global variable_metadata
    import json
    if json_str:
        variable_metadata = json.loads(json_str)
    else:
        variable_metadata = {}


def push_undo(description: str, edit_type: str = "", edit_detail: Optional[Dict] = None) -> None:
    """Push the current state onto the undo stack and clear redo."""
    global _undo_stack, _redo_stack
    action = EditAction(
        description=description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
        edit_type=edit_type,
        edit_detail=edit_detail or {},
    )
    _undo_stack.append(action)
    if len(_undo_stack) > _MAX_UNDO:
        _undo_stack.pop(0)
    _redo_stack.clear()  # new action invalidates redo


def undo() -> Optional[str]:
    """Undo the last action. Returns description or None if nothing to undo."""
    global _undo_stack, _redo_stack, current_data, variable_metadata
    if not _undo_stack:
        return None

    # Save current state to redo stack
    action = _undo_stack.pop()
    redo_action = EditAction(
        description=action.description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
    )
    _redo_stack.append(redo_action)

    # Restore previous state
    _restore_df(action.df_snapshot)
    _restore_meta(action.meta_snapshot)

    return action.description


def redo() -> Optional[str]:
    """Redo the last undone action. Returns description or None."""
    global _undo_stack, _redo_stack, current_data, variable_metadata
    if not _redo_stack:
        return None

    action = _redo_stack.pop()

    # Save current to undo
    undo_action = EditAction(
        description=action.description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
    )
    _undo_stack.append(undo_action)

    # Restore
    _restore_df(action.df_snapshot)
    _restore_meta(action.meta_snapshot)

    return action.description


def get_undo_info() -> Dict[str, Any]:
    """Return undo/redo stack info for the status bar."""
    return {
        "undo_count": len(_undo_stack),
        "redo_count": len(_redo_stack),
        "last_undo": _undo_stack[-1].description if _undo_stack else None,
        "last_redo": _redo_stack[-1].description if _redo_stack else None,
    }


def clear_history() -> None:
    """Clear undo/redo history (e.g. on new data load)."""
    global _undo_stack, _redo_stack
    _undo_stack.clear()
    _redo_stack.clear()


# ---------------------------------------------------------------------------
# Variable metadata helpers
# ---------------------------------------------------------------------------

def init_variable_metadata(df: pd.DataFrame) -> None:
    """Initialise variable metadata from a DataFrame's columns."""
    global variable_metadata
    variable_metadata.clear()
    if df is None:
        return
    for col in df.columns:
        dtype = df[col].dtype
        is_num = pd.api.types.is_numeric_dtype(dtype)
        is_date = pd.api.types.is_datetime64_any_dtype(dtype)

        if is_date:
            vtype = "date"
            measure = "scale"
        elif is_num:
            vtype = "numeric"
            # If few unique values, it's ordinal
            if df[col].nunique() <= 10:
                measure = "ordinal"
            else:
                measure = "scale"
        else:
            vtype = "string"
            measure = "nominal"

        variable_metadata[col] = {
            "name": col,
            "type": vtype,
            "width": 8 if is_num else 12,
            "decimals": 2 if is_num else 0,
            "label": "",
            "value_labels": {},
            "missing_values": [],
            "columns": 10,
            "align": "right" if is_num else "left",
            "measure": measure,
            "role": "input",
        }


def update_variable_meta(name: str, updates: Dict[str, Any]) -> bool:
    """Update metadata for a variable. Returns True if successful."""
    global variable_metadata
    if name not in variable_metadata:
        return False
    # Only allow known keys
    allowed = {"type", "width", "decimals", "label", "value_labels",
               "missing_values", "columns", "align", "measure", "role", "name"}
    for k, v in updates.items():
        if k in allowed:
            variable_metadata[name][k] = v
    return True
