"""
DevStat Backend — FastAPI Application Entry Point

Medical statistics software backend serving a Vue.js SPA frontend.
Provides REST API endpoints for data import, statistical analysis,
visualization, and diagnostic test evaluation.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import math
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.state import _session_id_var
from app.config import PROJECT_NAME, VERSION
from app.routers import data, analysis, charts, output, suggest, transform, wizard, r_status, eligibility, project, auth, license, teaching, questionbank
from app.config import OFFLINE
# AI assistant removed from the product — the router is not mounted (the ai
# package is present but intentionally disabled so /api/ai/* returns 404).
AI_AVAILABLE = False

# ── Analysis engine ───────────────────────────────────────────────────────
from r.engine import AnalysisEngine

# ── Startup dependency check ─────────────────────────────────────────────
from app.startup_check import run_startup_check
from app.logging_config import RequestLoggingMiddleware


# ---------------------------------------------------------------------------
# Custom JSON encoder — handles numpy/pandas types globally
# ---------------------------------------------------------------------------

class NumpyJSONResponse(JSONResponse):
    """JSONResponse that automatically converts numpy/pandas types."""

    def render(self, content: Any) -> bytes:
        sanitized = _sanitize_for_json(content)
        try:
            return json.dumps(
                sanitized,
                ensure_ascii=False,
                allow_nan=False,
                indent=None,
                separators=(",", ":"),
                default=_json_encoder_default,
            ).encode("utf-8")
        except Exception as exc:
            _write_crash(exc, content)
            # Fallback: re-serialize with allow_nan=True and convert nan to None
            return json.dumps(
                sanitized,
                ensure_ascii=False,
                allow_nan=True,
                indent=None,
                separators=(",", ":"),
                default=_json_encoder_default,
            ).replace(":NaN", ":null").replace(":-NaN", ":null").replace(":Infinity", ":null").replace(":-Infinity", ":null").encode("utf-8")


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replace non-JSON-safe float values (inf, nan) with None."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_sanitize_for_json(v) for v in obj)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def _json_encoder_default(obj: Any) -> Any:
    """Fallback for json.dumps — converts numpy/pandas types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (pd.Timedelta,)):
        return str(obj)
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _client_ip(request: Request) -> str:
    """First X-Forwarded-For value (set by Cloud Run) = the client IP."""
    try:
        ff = request.headers.get("x-forwarded-for", "") or ""
        return (ff.split(",", 1)[0] or "").strip()[:64]
    except Exception:  # noqa: BLE001
        return ""


def _write_crash(exc: Exception, content: Any = None) -> None:
    """Write exception traceback to a crash log file."""
    import traceback
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('TEMP', '.'))
    else:
        base = Path(__file__).resolve().parent.parent
    crash_log = base / "devstat_crash.log"
    try:
        with open(str(crash_log), "w") as f:
            f.write(f"Exception: {type(exc).__name__}: {exc}\n\n")
            f.write(traceback.format_exc())
            if content is not None:
                f.write(f"\n\nContent type: {type(content)}\n")
                f.write(f"Content (partial): {str(content)[:2000]}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance."""
    app = FastAPI(
        title=PROJECT_NAME,
        version=VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        default_response_class=NumpyJSONResponse,
    )

    # ---- Analysis engine startup ---------------------------------------------
    @app.on_event("startup")
    async def _startup_engine():
        """Initialize analysis engine in background — health responds immediately."""
        import threading
        threading.Thread(target=_init_engine, daemon=True, name="engine-init").start()

    def _init_engine():
        import logging
        slog = logging.getLogger("devstat.startup")
        slog.info("Engine init started in background thread")
        app.state.engine = AnalysisEngine()
        app.state.engine_type = "py"

        startup_report = run_startup_check()
        app.state.startup_report = startup_report
        n = len(app.state.engine.available_analyses())
        slog.info("Python engine active — %d analyses available", n)

    # ---- Request logging middleware — logs EVERYTHING ------------------------
    app.add_middleware(RequestLoggingMiddleware)

    # ---- CORS ----------------------------------------------------------------
    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:8150,http://localhost:8150").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Session isolation — each browser gets its own data ------------------
    @app.middleware("http")
    async def _session_middleware(request: Request, call_next):
        sid = request.cookies.get("session_id") or str(uuid.uuid4())
        token = _session_id_var.set(sid)
        from app import state as _state
        # App mode ('exam'|'live') + teaching flag must be set before anything is
        # restored so that LIVE (confidential) mode never re-loads stored data.
        _state.set_mode(request.headers.get("x-devstat-mode", ""))
        _state.set_teaching(request.headers.get("x-devstat-teaching", "") in ("1", "true", "yes"))
        # Machine + IP identity for the free-tier gate (bound to the physical
        # machine AND the address — never the session). It is independent of the
        # account so clearing cookies / making a new account cannot refresh the
        # used-up free allowance.
        _state.set_device(request.headers.get("x-devstat-device", ""))
        _state.set_client_ip(_client_ip(request))
        # Per-USER isolation: if a valid DevStat session token is present, key
        # the in-memory session by the user's uid (so no account can ever see
        # another account's data) and restore their stored dataset.
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            from app.services.session_guard import peek_uid
            uid = peek_uid(auth[7:].strip())
            if uid:
                _state.set_uid(uid)
                _state.restore_user_dataset()
        response = await call_next(request)
        response.set_cookie("session_id", sid, httponly=True, samesite="lax")
        _session_id_var.reset(token)
        return response

    # ---- API routers ---------------------------------------------------------
    app.include_router(data.router, prefix="/api/data", tags=["Data"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
    app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
    app.include_router(suggest.router, prefix="/api/analysis", tags=["Suggest Test"])
    app.include_router(output.router, prefix="/api/output", tags=["Output"])
    app.include_router(transform.router, prefix="/api/transform", tags=["Transform"])
    app.include_router(wizard.router, prefix="/api/wizard", tags=["Wizard"])
    app.include_router(r_status.router, prefix="/api", tags=["Health"])
    app.include_router(eligibility.router)
    app.include_router(project.router, prefix="/api")
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(license.router, prefix="/api", tags=["License"])
    app.include_router(teaching.router, prefix="/api", tags=["Teaching"])
    app.include_router(questionbank.router, prefix="/api", tags=["Question Bank"])

    # ---- Health check --------------------------------------------------------
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        """Return basic service health information."""
        cloud_run = bool(os.environ.get("K_SERVICE", ""))
        return {
            "status": "ok",
            "project": PROJECT_NAME,
            "version": VERSION,
            "engine": "py",
            "cloud_run": cloud_run,
            "desktop": OFFLINE,
            "ai_available": AI_AVAILABLE,
        }

    # ---- Global exception handler — logs crashes ---------------------------
    @app.exception_handler(Exception)
    async def _global_exception_handler(request, exc):
        _write_crash(exc)
        import traceback
        lines = traceback.format_exc().splitlines()
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {str(exc)}", "traceback": lines[-15:]},
        )

    # ---- Engine status -------------------------------------------------------
    @app.get("/api/r-status", tags=["Health"])
    async def engine_status():
        """Return engine status and available analyses."""
        engine = getattr(app.state, "engine", None)
        if engine is None:
            return {"engine": "unknown", "ok": False}
        return {
            "engine": "py",
            "ok": True,
            "analyses_loaded": len(engine.available_analyses()),
            "analyses": engine.available_analyses(),
        }

    # ---- Static files & SPA fallback -----------------------------------------
    _mount_static_files_and_spa_fallback(app)

    return app


def _mount_static_files_and_spa_fallback(app: FastAPI) -> None:
    """Serve the built frontend SPA from ``frontend/dist``."""
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "static"

    if not dist_dir.is_dir():
        return

    @app.get("/", include_in_schema=False)
    async def _serve_root() -> FileResponse:
        index = dist_dir / "index.html"
        return FileResponse(str(index))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_frontend(full_path: str) -> FileResponse:
        """Serve static files, falling back to index.html for SPA routes."""
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        index = dist_dir / "index.html"
        if not index.exists():
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        if not full_path:
            return FileResponse(str(index))

        requested = dist_dir / full_path
        if requested.exists() and requested.is_file():
            return FileResponse(str(requested))

        with_html = dist_dir / f"{full_path}.html"
        if with_html.exists():
            return FileResponse(str(with_html))

        return FileResponse(str(index))


# ---------------------------------------------------------------------------
# ASGI entry point
# ---------------------------------------------------------------------------

app = create_app()
