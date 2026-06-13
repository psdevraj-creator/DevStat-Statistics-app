"""
Backend logging configuration — logs EVERYTHING to devstat.log.

Captures all API requests/responses, service calls, R bridge operations,
data mutations, and errors with full context for debugging.
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "devstat.log"

# ── File handler — everything at DEBUG+ ──────────────────────────────
file_handler = logging.FileHandler(str(LOG_FILE), mode="w", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
))

# Console handler — INFO+ to stderr
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
))

# Root logger
root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.DEBUG)

# ── Named loggers for each subsystem ─────────────────────────────────
api_logger = logging.getLogger("devstat.api")
service_logger = logging.getLogger("devstat.service")
r_bridge_logger = logging.getLogger("devstat.r_bridge")
data_logger = logging.getLogger("devstat.data")
elig_logger = logging.getLogger("devstat.eligibility")


# ── Request logging middleware ────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every API request and response with timing and body."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = f"{time.time_ns():x}"
        start = time.time()

        # Log request
        body = None
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                body_bytes = await request.body()
                if body_bytes:
                    body = body_bytes.decode("utf-8", errors="replace")[:5000]
        except Exception:
            pass

        api_logger.info(
            "REQ  | id=%s | %s %s | body=%s",
            req_id, request.method, request.url.path,
            body[:200] if body else "(empty)",
        )

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = time.time() - start
            api_logger.error(
                "REQ_CRASH | id=%s | %s %s | elapsed=%.3fs | error=%s | trace=%s",
                req_id, request.method, request.url.path, elapsed,
                str(e), traceback.format_exc()[-2000:],
            )
            raise

        elapsed = time.time() - start

        # Log response
        resp_body = None
        try:
            if hasattr(response, "body"):
                resp_body = response.body.decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass

        log_level = api_logger.info if response.status_code < 400 else api_logger.warning
        log_level(
            "RESP | id=%s | %s %s | status=%d | elapsed=%.3fs | body=%s",
            req_id, request.method, request.url.path,
            response.status_code, elapsed,
            resp_body[:500] if resp_body else "(streaming)",
        )

        return response


# ── Helper loggers ────────────────────────────────────────────────────

def log_r_bridge_call(analysis: str, params: dict, result: dict, elapsed: float):
    """Log an R bridge execution with params and result summary."""
    r_bridge_logger.info(
        "R_CALL | analysis=%s | params=%s | result_ok=%s | elapsed=%.3fs | error=%s",
        analysis,
        json.dumps({k: v for k, v in params.items() if k != "data_path"}, default=str)[:1000],
        "error" not in result,
        elapsed,
        result.get("error", "")[:500],
    )


def log_service_call(service: str, method: str, args_summary: str, result_summary: str, elapsed: float):
    """Log a service-layer function call."""
    service_logger.debug(
        "SERVICE | %s.%s | args=%s | elapsed=%.3fs | result=%s",
        service, method, args_summary, elapsed, result_summary[:500],
    )


def log_data_mutation(operation: str, detail: str, result: dict):
    """Log a data mutation (upload, edit, compute, recode, etc.)."""
    data_logger.info(
        "MUTATION | op=%s | detail=%s | result=%s",
        operation, detail, json.dumps(result, default=str)[:1000],
    )


def log_eligibility_failure(endpoint: str, action: str, error: str):
    """Log an eligibility engine failure with endpoint context."""
    elig_logger.warning(
        "ELIGIBILITY_FAILURE | endpoint=%s | action=%s | error=%s",
        endpoint, action, error,
    )


def log_endpoint_error(endpoint: str, method: str, error: str):
    """Log an unexpected endpoint error."""
    api_logger.error(
        "ENDPOINT_ERROR | endpoint=%s | method=%s | %s",
        endpoint, method, error,
    )


def log_safe_interpret(func_name: str, error: str, result_keys: list):
    """Log when _safe_interpret swallows an exception."""
    service_logger.warning(
        "INTERPRET_CRASH | func=%s | error=%s | result_keys=%s",
        func_name, error, result_keys[:10],
    )
