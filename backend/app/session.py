from __future__ import annotations

import copy
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Per-session state container
# ---------------------------------------------------------------------------

@dataclass
class EditAction:
    description: str = ""
    df_snapshot: Optional[str] = None
    meta_snapshot: Optional[str] = None
    edit_type: str = ""
    edit_detail: Dict[str, Any] = field(default_factory=dict)


_MAX_UNDO = 100
_SESSION_TTL = 3600  # 1 hour idle timeout


class SessionData:
    """Holds all mutable state for one user session."""

    def __init__(self) -> None:
        self.current_data: Optional[pd.DataFrame] = None
        self.current_filename: str = ""
        self.variable_metadata: Dict[str, Dict[str, Any]] = {}
        self._undo_stack: List[EditAction] = []
        self._redo_stack: List[EditAction] = []
        self._cached_metadata: Optional[Dict[str, Any]] = None
        self._split_var: Optional[str] = None
        self._weight_var: Optional[str] = None
        self.created_at: float = time.time()
        self.last_active: float = time.time()

    def touch(self) -> None:
        self.last_active = time.time()

    # ── Snapshots ──────────────────────────────────────────────────────────

    def _snapshot_df(self) -> str:
        if self.current_data is None:
            return ""
        return self.current_data.to_csv(index=False)

    def _snapshot_meta(self) -> str:
        import json
        return json.dumps(self.variable_metadata, default=str)

    def _restore_df(self, csv_str: str) -> None:
        if csv_str:
            from io import StringIO
            self.current_data = pd.read_csv(StringIO(csv_str))
        else:
            self.current_data = None

    def _restore_meta(self, json_str: str) -> None:
        import json
        if json_str:
            self.variable_metadata = json.loads(json_str)
        else:
            self.variable_metadata = {}

    # ── Undo / Redo ────────────────────────────────────────────────────────

    def push_undo(self, description: str, edit_type: str = "",
                  edit_detail: Optional[Dict] = None) -> None:
        action = EditAction(
            description=description,
            df_snapshot=self._snapshot_df(),
            meta_snapshot=self._snapshot_meta(),
            edit_type=edit_type,
            edit_detail=edit_detail or {},
        )
        self._undo_stack.append(action)
        if len(self._undo_stack) > _MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> Optional[str]:
        if not self._undo_stack:
            return None
        action = self._undo_stack.pop()
        redo_action = EditAction(
            description=action.description,
            df_snapshot=self._snapshot_df(),
            meta_snapshot=self._snapshot_meta(),
        )
        self._redo_stack.append(redo_action)
        self._restore_df(action.df_snapshot)
        self._restore_meta(action.meta_snapshot)
        return action.description

    def redo(self) -> Optional[str]:
        if not self._redo_stack:
            return None
        action = self._redo_stack.pop()
        undo_action = EditAction(
            description=action.description,
            df_snapshot=self._snapshot_df(),
            meta_snapshot=self._snapshot_meta(),
        )
        self._undo_stack.append(undo_action)
        self._restore_df(action.df_snapshot)
        self._restore_meta(action.meta_snapshot)
        return action.description

    def get_undo_info(self) -> Dict[str, Any]:
        return {
            "undo_count": len(self._undo_stack),
            "redo_count": len(self._redo_stack),
            "last_undo": self._undo_stack[-1].description if self._undo_stack else None,
            "last_redo": self._redo_stack[-1].description if self._redo_stack else None,
        }

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ── Variable metadata helpers ──────────────────────────────────────────

    def init_variable_metadata(self, df: Optional[pd.DataFrame]) -> None:
        self.variable_metadata.clear()
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
            self.variable_metadata[col] = {
                "name": col, "type": vtype, "width": 8 if is_num else 12,
                "decimals": 2 if is_num else 0, "label": "",
                "value_labels": {}, "missing_values": [],
                "columns": 10, "align": "right" if is_num else "left",
                "measure": measure, "role": "input",
            }

    def update_variable_meta(self, name: str, updates: Dict[str, Any]) -> bool:
        if name not in self.variable_metadata:
            return False
        allowed = {"type", "width", "decimals", "label", "value_labels",
                   "missing_values", "columns", "align", "measure", "role", "name"}
        for k, v in updates.items():
            if k in allowed:
                self.variable_metadata[name][k] = v
        return True


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """Creates and tracks user sessions, with idle-timeout cleanup."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionData] = {}
        self._default: Optional[SessionData] = None

    def get_or_create(self, session_id: str) -> SessionData:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData()
        session = self._sessions[session_id]
        session.touch()
        return session

    def get_default(self) -> SessionData:
        if self._default is None:
            self._default = SessionData()
        return self._default

    def cleanup(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > _SESSION_TTL
        ]
        for sid in expired:
            del self._sessions[sid]


manager = SessionManager()
