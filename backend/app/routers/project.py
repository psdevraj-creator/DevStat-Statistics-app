from __future__ import annotations

import io
import json
import zipfile
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import Response

import app.state as _state
from app.state import require_data
from app.config import VERSION

router = APIRouter(prefix="/project", tags=["Project"])


@router.post("/save")
async def save_project(request: Request) -> Response:
    """Save current session to a .devstat file."""
    body = await request.json()
    outputs = body.get("outputs", [])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        state = _state.get_session_state()
        state["version"] = VERSION
        zf.writestr("state.json", json.dumps(state, default=str))

        csv_str = _state.get_current_data_csv()
        zf.writestr("data.csv", csv_str)

        zf.writestr("outputs.json", json.dumps(outputs, default=str))

    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="project.devstat"'},
    )


@router.post("/load")
async def load_project(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Load a .devstat file and restore the session."""
    if not file.filename or not file.filename.endswith(".devstat"):
        raise HTTPException(400, "File must have .devstat extension")

    try:
        raw = await file.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            if "state.json" not in zf.namelist():
                raise HTTPException(400, "Invalid project file: missing state.json")

            state = json.loads(zf.read("state.json"))

            csv_str = ""
            if "data.csv" in zf.namelist():
                csv_str = zf.read("data.csv").decode("utf-8")

            outputs_raw = zf.read("outputs.json") if "outputs.json" in zf.namelist() else b"[]"
            outputs = json.loads(outputs_raw)

            _state.restore_session(state, csv_str)

            return {
                "status": "ok",
                "filename": state.get("current_filename", ""),
                "rows": len(csv_str.strip().split("\n")) - 1 if csv_str.strip() else 0,
                "outputs": outputs,
            }
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid project file: not a valid ZIP")
    except Exception as e:
        raise HTTPException(400, f"Failed to load project: {e}")
