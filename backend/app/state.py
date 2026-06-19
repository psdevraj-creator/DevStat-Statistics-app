from __future__ import annotations

import contextvars
import sys
import types
from typing import Any, Dict, Optional

import pandas as pd

from app.session import manager as _session_manager

# ---------------------------------------------------------------------------
# Per-request session routing via contextvars
# ---------------------------------------------------------------------------

_session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('session_id', default='')


def _get_session():
    """Return the SessionData for the current request context."""
    sid = _session_id_var.get()
    if not sid:
        return _session_manager.get_default()
    return _session_manager.get_or_create(sid)


_SESSION_ATTRS = frozenset({
    'current_data', 'current_filename', 'variable_metadata',
    '_undo_stack', '_redo_stack', '_cached_metadata',
    '_split_var', '_weight_var',
})


class _SessionStateModule(types.ModuleType):
    """Module subclass that routes session attributes through contextvars."""

    def __getattr__(self, name: str) -> Any:
        if name in _SESSION_ATTRS:
            return getattr(_get_session(), name)
        raise AttributeError(f"module 'app.state' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _SESSION_ATTRS:
            setattr(_get_session(), name, value)
            return
        super().__setattr__(name, value)


# Replace this module's class so `import app.state as _state` routes through us
if sys.modules.get(__name__) is not None:
    sys.modules[__name__].__class__ = _SessionStateModule


# ---------------------------------------------------------------------------
# Public API — kept unchanged so existing imports keep working
# ---------------------------------------------------------------------------

def init_session(session_id: str) -> None:
    """Called by middleware to bind the current request to a session."""
    _session_id_var.set(session_id)


def require_data() -> None:
    from fastapi import HTTPException
    session = _get_session()
    if session.current_data is None:
        raise HTTPException(
            status_code=400,
            detail="No dataset is currently loaded. Upload a file first.",
        )


def init_variable_metadata(df: Optional[pd.DataFrame]) -> None:
    _get_session().init_variable_metadata(df)


def update_variable_meta(name: str, updates: Dict[str, Any]) -> bool:
    return _get_session().update_variable_meta(name, updates)


def push_undo(description: str, edit_type: str = "",
              edit_detail: Optional[Dict] = None) -> None:
    _get_session().push_undo(description, edit_type, edit_detail)


def undo() -> Optional[str]:
    return _get_session().undo()


def redo() -> Optional[str]:
    return _get_session().redo()


def get_undo_info() -> Dict[str, Any]:
    return _get_session().get_undo_info()


def clear_history() -> None:
    _get_session().clear_history()
