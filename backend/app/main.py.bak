"""
DevStat Backend — FastAPI Application Entry Point

Medical statistics software backend serving a Vue.js SPA frontend.
Provides REST API endpoints for data import, statistical analysis,
visualization, and diagnostic test evaluation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import math
import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.state import current_data, current_filename
from app.config import PROJECT_NAME, VERSION
from app.routers import data, analysis, charts, output, suggest, transform, wizard, r_status, syntax, eligibility

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
        return json.dumps(
            sanitized,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=_json_encoder_default,
        ).encode("utf-8")


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
        """Create analysis engine and verify dependencies."""
        import logging
        slog = logging.getLogger("devstat.startup")

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

    # ---- API routers ---------------------------------------------------------
    app.include_router(data.router, prefix="/api/data", tags=["Data"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
    app.include_router(charts.router, prefix="/api/charts", tags=["Charts"])
    app.include_router(suggest.router, prefix="/api/analysis", tags=["Suggest Test"])
    app.include_router(output.router, prefix="/api/output", tags=["Output"])
    app.include_router(transform.router, prefix="/api/transform", tags=["Transform"])
    app.include_router(wizard.router, prefix="/api/wizard", tags=["Wizard"])
    app.include_router(r_status.router, prefix="/api", tags=["Health"])
    app.include_router(syntax.router, prefix="/api/syntax", tags=["Syntax"])
    app.include_router(eligibility.router)

    # ---- Health check --------------------------------------------------------
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        """Return basic service health information."""
        return {
            "status": "ok",
            "project": PROJECT_NAME,
            "version": VERSION,
            "data_loaded": current_data is not None,
            "filename": current_filename,
            "engine": "py",
        }

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
