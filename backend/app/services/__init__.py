"""
Shared helpers for DevStat service modules.
"""

from typing import Any, Dict, Optional


def error(
    message: str,
    detail: Optional[str] = None,
    suggestion: Optional[str] = None,
    help_topic: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a standardised error response dict.

    All service functions should use this instead of raw ``{"error": ...}``
    so that the frontend receives consistent, user-friendly error messages.

    Backward-compatible: ``result["error"]`` still holds the message string,
    so existing router code that checks ``if result.get("error")`` works
    without changes.

    Parameters
    ----------
    message : str
        Short, plain-English explanation shown to the user.
    detail : str, optional
        Technical detail (e.g., which column, what value).  Shown below the
        message in a lighter style.
    suggestion : str, optional
        What the user can do to fix the problem.
    help_topic : str, optional
        A key into the glossary/help system (see ``helpContent.ts``).

    Returns
    -------
    dict
        ``{"error": <message>, "message": <message>, "detail": ...,
        "suggestion": ..., "help_topic": ...}``
    """
    return {
        "error": message,
        "message": message,
        "detail": detail or "",
        "suggestion": suggestion or "",
        "help_topic": help_topic or "",
    }
