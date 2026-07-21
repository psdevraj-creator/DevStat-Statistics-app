from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import HTTPException

_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id")
_sessions: Dict[str, dict] = {}


_DUMMY_SESSION = {"current_data": None, "current_filename": "", "variable_metadata": {}, "_undo_stack": [], "_redo_stack": []}


def _session() -> dict:
    try:
        sid = _session_id_var.get()
    except LookupError:
        return _DUMMY_SESSION
    if sid not in _sessions:
        _sessions[sid] = {
            "current_data": None,
            "current_filename": "",
            "variable_metadata": {},
            "_undo_stack": [],
            "_redo_stack": [],
        }
    return _sessions[sid]


def __getattr__(name: str) -> Any:
    s = _session()
    if name in ("current_data", "current_filename", "variable_metadata", "_undo_stack", "_redo_stack"):
        return s[name]
    raise AttributeError(f"module 'state' has no attribute '{name}'")


def set_current_data(df):
    _session()["current_data"] = df


def set_current_filename(name: str):
    _session()["current_filename"] = name


def clear_current_data():
    s = _session()
    s["current_data"] = None
    s["current_filename"] = ""


def _get(key: str) -> Any:
    return _session()[key]


def _set(key: str, val: Any) -> None:
    _session()[key] = val


def require_data() -> None:
    if _get("current_data") is None:
        raise HTTPException(
            status_code=400,
            detail="No dataset is currently loaded. Upload a file first.",
        )


@dataclass
class EditAction:
    description: str
    df_snapshot: Optional[str] = None
    meta_snapshot: Optional[str] = None
    edit_type: str = ""
    edit_detail: Dict[str, Any] = field(default_factory=dict)


_MAX_UNDO = 100


def _snapshot_df() -> str:
    df = _get("current_data")
    if df is None:
        return ""
    return df.to_csv(index=False)


def _snapshot_meta() -> str:
    import json
    return json.dumps(_get("variable_metadata"), default=str)


def _restore_df(csv_str: str) -> None:
    if csv_str:
        from io import StringIO
        _set("current_data", pd.read_csv(StringIO(csv_str)))
    else:
        _set("current_data", None)


def _restore_meta(json_str: str) -> None:
    import json
    _set("variable_metadata", json.loads(json_str) if json_str else {})


def push_undo(description: str, edit_type: str = "", edit_detail: Optional[Dict] = None) -> None:
    s = _session()
    action = EditAction(
        description=description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
        edit_type=edit_type,
        edit_detail=edit_detail or {},
    )
    s["_undo_stack"].append(action)
    if len(s["_undo_stack"]) > _MAX_UNDO:
        s["_undo_stack"].pop(0)
    s["_redo_stack"].clear()


def undo() -> Optional[str]:
    s = _session()
    if not s["_undo_stack"]:
        return None
    action = s["_undo_stack"].pop()
    redo_action = EditAction(
        description=action.description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
    )
    s["_redo_stack"].append(redo_action)
    _restore_df(action.df_snapshot)
    _restore_meta(action.meta_snapshot)
    return action.description


def redo() -> Optional[str]:
    s = _session()
    if not s["_redo_stack"]:
        return None
    action = s["_redo_stack"].pop()
    undo_action = EditAction(
        description=action.description,
        df_snapshot=_snapshot_df(),
        meta_snapshot=_snapshot_meta(),
    )
    s["_undo_stack"].append(undo_action)
    _restore_df(action.df_snapshot)
    _restore_meta(action.meta_snapshot)
    return action.description


def get_undo_info() -> Dict[str, Any]:
    s = _session()
    return {
        "undo_count": len(s["_undo_stack"]),
        "redo_count": len(s["_redo_stack"]),
        "last_undo": s["_undo_stack"][-1].description if s["_undo_stack"] else None,
        "last_redo": s["_redo_stack"][-1].description if s["_redo_stack"] else None,
    }


def clear_history() -> None:
    s = _session()
    s["_undo_stack"].clear()
    s["_redo_stack"].clear()


def init_variable_metadata(df: pd.DataFrame) -> None:
    meta = _get("variable_metadata")
    meta.clear()
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
            measure = "ordinal" if df[col].nunique() <= 10 else "scale"
        else:
            vtype = "string"
            measure = "nominal"
        meta[col] = {
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
    meta = _get("variable_metadata")
    if name not in meta:
        return False
    allowed = {"type", "width", "decimals", "label", "value_labels",
               "missing_values", "columns", "align", "measure", "role", "name"}
    for k, v in updates.items():
        if k in allowed:
            meta[name][k] = v
    return True
