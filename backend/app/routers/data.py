"""
DevStat — Data Router

Endpoints for uploading, inspecting, editing, and exporting datasets.
Mounted at ``/api/data`` in the main FastAPI application.
Supports SPSS-like variable metadata, undo/redo, and row/column CRUD.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

import app.state as _state
from app.logging_config import log_data_mutation
from app.state import (
    init_variable_metadata,
    update_variable_meta,
    push_undo,
    undo,
    redo,
    get_undo_info,
    clear_history,
    require_data,
)
from app.models.dataset import (
    CellEdit,
    DatasetInfo,
    ColumnInfo,
    VariableMetaUpdate,
    ValueLabelSet,
    MissingValueSet,
    AddColumnRequest,
    UndoRedoResponse,
    ComputeRequest,
    RecodeRequest,
    SurvivalPrepResponse,
)
from app.services.importer import get_column_info, import_file

router = APIRouter(prefix="", tags=["Data"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_require_data = require_data


def _preview(df: pd.DataFrame, n: int = 500) -> List[Dict[str, Any]]:
    """Return the first *n* rows as JSON-safe dicts."""
    preview_df = df.head(n)
    return preview_df.where(pd.notna(preview_df), None).to_dict(orient="records")


def _serialize_value(val: Any) -> Any:
    """Convert a scalar to JSON-safe value, replacing NaN/NaT with None."""
    if pd.isna(val):
        return None
    if isinstance(val, (pd.Timestamp, pd.Period)):
        return str(val)
    if hasattr(val, "item"):
        return val.item()
    return val


def _build_column_info(df: pd.DataFrame) -> List[ColumnInfo]:
    """Build ColumnInfo list from DataFrame, merging with stored metadata."""
    base_cols = get_column_info(df)
    result = []
    for col_dict in base_cols:
        name = col_dict["name"]
        meta = _state.variable_metadata.get(name, {})
        result.append(ColumnInfo(
            name=name,
            dtype=col_dict.get("dtype", "string"),
            unique_count=col_dict.get("unique_count", 0),
            missing_count=col_dict.get("missing_count", 0),
            missing_pct=col_dict.get("missing_pct", 0.0),
            is_numeric=col_dict.get("is_numeric", False),
            is_categorical=col_dict.get("is_categorical", False),
            labels=col_dict.get("labels"),
            type=meta.get("type", col_dict.get("type", "numeric")),
            width=meta.get("width", col_dict.get("width", 8)),
            decimals=meta.get("decimals", col_dict.get("decimals", 2)),
            label=meta.get("label", ""),
            value_labels=meta.get("value_labels", {}),
            missing_values=meta.get("missing_values", []),
            columns=meta.get("columns", 10),
            align=meta.get("align", "right" if col_dict.get("is_numeric", False) else "left"),
            measure=meta.get("measure", "scale" if col_dict.get("is_numeric", False) else "nominal"),
            role=meta.get("role", "input"),
        ))
    return result


def _build_dataset_info(df: pd.DataFrame, name: str) -> DatasetInfo:
    """Build a DatasetInfo response."""
    rows, cols = df.shape
    column_infos = _build_column_info(df)
    return DatasetInfo(
        name=name,
        rows=rows,
        cols=cols,
        columns=column_infos,
        preview=_preview(df),
    )


# ---------------------------------------------------------------------------
# Data Upload & Info
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=DatasetInfo)
async def upload_file(file: UploadFile = File(...)) -> DatasetInfo:
    """Upload a data file (CSV, Excel, SPSS .sav, Stata .dta)."""
    # Using _state.current_data / _state.current_filename

    if file.filename is None or file.filename.strip() == "":
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".tsv", ".xlsx", ".xls", ".sav", ".dta"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix}'. Supported: .csv, .tsv, .xlsx, .xls, .sav, .dta",
        )

    # Save to temp
    try:
        tmp_dir = tempfile.mkdtemp(prefix="devstat_")
        tmp_path = Path(tmp_dir) / file.filename
        content = await file.read()
        tmp_path.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}")

    # Import
    try:
        df = import_file(str(tmp_path))
    except Exception as exc:
        _cleanup_temp(tmp_dir)
        raise HTTPException(status_code=422, detail=f"Failed to import file: {exc}")
    finally:
        _cleanup_temp(tmp_dir)

    # Update state
    _state.current_data = df
    _state.current_filename = file.filename
    init_variable_metadata(df)
    clear_history()
    _invalidate_metadata_cache()

    return _build_dataset_info(df, name=file.filename)


def _cleanup_temp(tmp_dir: str) -> None:
    """Remove a temp directory."""
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@router.get("/info")
async def dataset_info() -> Optional[DatasetInfo]:
    """Return metadata and a preview of the currently loaded dataset."""
    if _state.current_data is None:
        return None
    return _build_dataset_info(_state.current_data, name=_state.current_filename or "untitled")


@router.get("/columns")
async def column_info() -> List[Dict[str, Any]]:
    """Return per-column metadata for the currently loaded dataset."""
    _require_data()
    cols = _build_column_info(_state.current_data)
    return [c.model_dump() for c in cols]


@router.get("/preview")
async def preview_data(n: int = 100) -> List[Dict[str, Any]]:
    """Return the first *n* rows (max 500)."""
    if _state.current_data is None:
        return []
    return _preview(_state.current_data, n=min(n, 500))


# ---------------------------------------------------------------------------
# Server-side data grid — pagination, sort, filter
# ---------------------------------------------------------------------------

@router.post("/rows")
async def paginated_rows(body: Dict[str, Any]) -> Dict[str, Any]:
    """Return paginated rows with server-side sort and filter.

    Request body::

        {
          "page": 0,
          "pageSize": 100,
          "sortModel": [{"colId": "age", "sort": "asc"}],
          "filterModel": {"age": {"filterType": "number", "type": "greaterThan", "filter": 30}}
        }
    """
    _require_data()
    df = _state.current_data

    page = max(0, body.get("page", 0))
    page_size = min(body.get("pageSize", 100), 1000)
    sort_model = body.get("sortModel") or []
    filter_model = body.get("filterModel") or {}

    # Apply filters (AG Grid simple filter model)
    filtered = df
    for col_id, fm in filter_model.items():
        if col_id not in filtered.columns:
            continue
        ft = fm.get("filterType", "text")
        ftype = fm.get("type", "contains")
        val = fm.get("filter")

        if val is None or val == "":
            continue

        try:
            if ft == "number":
                col = pd.to_numeric(filtered[col_id], errors="coerce")
                num_val = float(val)
                if ftype == "equals":
                    filtered = filtered[col == num_val]
                elif ftype == "notEqual":
                    filtered = filtered[col != num_val]
                elif ftype == "greaterThan":
                    filtered = filtered[col > num_val]
                elif ftype == "lessThan":
                    filtered = filtered[col < num_val]
                elif ftype == "greaterThanOrEqual":
                    filtered = filtered[col >= num_val]
                elif ftype == "lessThanOrEqual":
                    filtered = filtered[col <= num_val]
                elif ftype == "inRange":
                    val_to = fm.get("filterTo")
                    if val_to is not None:
                        filtered = filtered[(col >= num_val) & (col <= float(val_to))]
            else:
                col = filtered[col_id].astype(str)
                str_val = str(val).lower()
                if ftype == "equals":
                    filtered = filtered[col.str.lower() == str_val]
                elif ftype == "notEqual":
                    filtered = filtered[col.str.lower() != str_val]
                elif ftype == "contains":
                    filtered = filtered[col.str.lower().str.contains(str_val, na=False)]
                elif ftype == "startsWith":
                    filtered = filtered[col.str.lower().str.startswith(str_val, na=False)]
        except Exception:
            continue

    total = len(filtered)

    # Apply sorting
    if sort_model:
        sort_cols = []
        sort_asc = []
        for sm in sort_model:
            cid = sm.get("colId", "")
            if cid in filtered.columns:
                sort_cols.append(cid)
                sort_asc.append(sm.get("sort", "asc") == "asc")
        if sort_cols:
            filtered = filtered.sort_values(by=sort_cols, ascending=sort_asc, na_position="last")

    # Paginate
    start = page * page_size
    rows = (
        filtered.iloc[start : start + page_size]
        .where(pd.notna(filtered), None)
        .to_dict(orient="records")
    )

    # Convert non-serializable values
    clean_rows = []
    for row in rows:
        clean_rows.append({k: _serialize_value(v) for k, v in row.items()})

    return {"rows": clean_rows, "total": total, "page": page, "pageSize": page_size}


# ---------------------------------------------------------------------------
# Metadata cache (cleared on upload, recomputed lazily)
# ---------------------------------------------------------------------------


def _invalidate_metadata_cache() -> None:
    _state._cached_metadata = None


@router.get("/metadata")
async def cached_metadata() -> Dict[str, Any]:
    """Return cached column metadata (avoids recomputation on every call)."""
    _require_data()
    if _state._cached_metadata is None:
        df = _state.current_data
        cols = _build_column_info(df)
        _state._cached_metadata = {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": [c.model_dump() for c in cols],
            "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        }
    return _state._cached_metadata


@router.get("/download")
async def download_csv() -> Response:
    """Export the currently loaded dataset as CSV."""
    _require_data()
    stream = io.StringIO()
    _state.current_data.to_csv(stream, index=False)
    stream.seek(0)
    download_name = (
        Path(_state.current_filename).stem + "_export.csv"
        if _state.current_filename
        else "export.csv"
    )
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/download/excel")
async def download_excel(body: Optional[Dict[str, Any]] = None) -> Response:
    """Export the currently loaded dataset as an Excel (.xlsx) file.

    Uses xlsxwriter for formatting.
    """
    _require_data()
    columns = (body or {}).get("columns")
    df = _state.current_data
    if columns:
        df = df[[c for c in columns if c in df.columns]]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
        workbook = writer.book
        worksheet = writer.sheets["Data"]

        # Format header.
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#005eb8",
            "font_color": "#ffffff",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)

        # Auto-fit column widths.
        for i, col in enumerate(df.columns):
            column_width = max(df[col].astype(str).str.len().max(), len(str(col))) + 2
            worksheet.set_column(i, i, min(column_width, 50))

    output.seek(0)
    download_name = (
        Path(_state.current_filename).stem + "_export.xlsx"
        if _state.current_filename
        else "export.xlsx"
    )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


# ---------------------------------------------------------------------------
# R / haven export helpers
# ---------------------------------------------------------------------------

_SUPPORTED_EXPORT_FORMATS = {"sav", "dta", "xpt"}

_CONTENT_TYPE_MAP = {
    "sav": "application/x-spss-sav",
    "dta": "application/x-stata-dta",
    "xpt": "application/x-sas-transport",
}

_EXT_MAP = {
    "sav": ".sav",
    "dta": ".dta",
    "xpt": ".xpt",
}


def _run_haven_export(format_suffix: str) -> bytes:
    """Common logic for R / haven export: write temp CSV, run Rscript,
    return the resulting binary bytes."""
    fmt = format_suffix.lstrip(".")  # normalise
    content_type = _CONTENT_TYPE_MAP[fmt]
    ext = _EXT_MAP[fmt]

    _require_data()
    df = _state.current_data

    try:
        # ---- write temp CSV ----
        csv_fd, csv_path = tempfile.mkstemp(suffix=".csv")
        os.close(csv_fd)
        df.to_csv(csv_path, index=False)

        # ---- write temp R script ----
        r_fd, r_path = tempfile.mkstemp(suffix=".R")
        os.close(r_fd)

        # ---- temp output file ----
        out_fd, out_path = tempfile.mkstemp(suffix=ext)
        os.close(out_fd)

        # MSYS: R wants forward slashes
        csv_posix = Path(csv_path).as_posix()
        out_posix = Path(out_path).as_posix()

        r_code = (
            f'df <- read.csv("{csv_posix}", stringsAsFactors = FALSE)\n'
            f'library(haven, quietly = TRUE)\n'
            f'haven::write_{fmt}(df, "{out_posix}")\n'
        )
        with open(r_path, "w", encoding="utf-8") as fh:
            fh.write(r_code)

        result = subprocess.run(
            ["Rscript", r_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"R / haven export failed (exit {result.returncode}): "
                f"{result.stderr or result.stdout}",
            )

        with open(out_path, "rb") as fh:
            payload = fh.read()

        if not payload:
            raise HTTPException(
                status_code=500,
                detail="R / haven export produced an empty file.",
            )

        return payload

    finally:
        for p in (csv_path, r_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


@router.post("/download/sav")
async def download_sav() -> Response:
    """Export current dataset as SPSS .sav via R / haven::write_sav()."""
    payload = _run_haven_export("sav")
    download_name = (
        Path(_state.current_filename).stem + "_export.sav"
        if _state.current_filename
        else "export.sav"
    )
    return StreamingResponse(
        iter([payload]),
        media_type=_CONTENT_TYPE_MAP["sav"],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/download/dta")
async def download_dta() -> Response:
    """Export current dataset as Stata .dta via R / haven::write_dta()."""
    payload = _run_haven_export("dta")
    download_name = (
        Path(_state.current_filename).stem + "_export.dta"
        if _state.current_filename
        else "export.dta"
    )
    return StreamingResponse(
        iter([payload]),
        media_type=_CONTENT_TYPE_MAP["dta"],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/download/xpt")
async def download_xpt() -> Response:
    """Export current dataset as SAS XPORT .xpt via R / haven::write_xpt()."""
    payload = _run_haven_export("xpt")
    download_name = (
        Path(_state.current_filename).stem + "_export.xpt"
        if _state.current_filename
        else "export.xpt"
    )
    return StreamingResponse(
        iter([payload]),
        media_type=_CONTENT_TYPE_MAP["xpt"],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.post("/download/multiformat")
async def download_multiformat(body: Dict[str, Any]) -> Response:
    """Export the dataset in a format selected via the request body.

    Body (JSON):
        {"format": "sav"}   — dispatches to the sav / dta / xpt endpoint
    """
    fmt = (body or {}).get("format", "").strip().lower()
    if fmt not in _SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{fmt}'. Supported: {', '.join(sorted(_SUPPORTED_EXPORT_FORMATS))}",
        )
    # Dispatch to the common helper
    payload = _run_haven_export(fmt)
    ext = _EXT_MAP[fmt]
    download_name = (
        Path(_state.current_filename).stem + f"_export{ext}"
        if _state.current_filename
        else f"export{ext}"
    )
    return StreamingResponse(
        iter([payload]),
        media_type=_CONTENT_TYPE_MAP[fmt],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@router.delete("/reset")
async def reset_data() -> Dict[str, str]:
    """Clear the currently loaded dataset from memory."""
    # Using _state.current_data / _state.current_filename
    _state.current_data = None
    _state.current_filename = ""
    _state.variable_metadata.clear()
    clear_history()
    _invalidate_metadata_cache()
    return {"status": "ok", "message": "Dataset has been cleared."}


# ---------------------------------------------------------------------------
# Cell Editing
# ---------------------------------------------------------------------------


@router.put("/cell")
async def edit_cell(edit: CellEdit) -> Dict[str, Any]:
    """Edit a single cell with undo support."""
    _require_data()

    if edit.col not in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Column '{edit.col}' not found.")
    if edit.row < 0 or edit.row >= len(_state.current_data):
        raise HTTPException(status_code=400, detail=f"Row index {edit.row} out of bounds.")

    # Save old value for undo
    old_val = _state.current_data.iloc[edit.row][edit.col]
    edit.old_value = _serialize_value(old_val)

    # Push undo before editing
    push_undo(
        description=f"Edit cell [{edit.row}, '{edit.col}']",
        edit_type="cell",
        edit_detail={"row": edit.row, "col": edit.col, "old_value": edit.old_value, "new_value": edit.value},
    )

    try:
        _state.current_data.loc[edit.row, edit.col] = edit.value
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to set cell value: {exc}")

    row = _state.current_data.iloc[edit.row].to_dict()
    _invalidate_metadata_cache()
    return {k: _serialize_value(v) for k, v in row.items()}


@router.put("/cells/batch")
async def edit_cells(edits: List[CellEdit]) -> Dict[str, Any]:
    """Batch edit multiple cells with a single undo point."""
    _require_data()
    if not edits:
        return {"status": "ok", "updated": 0}

    push_undo(description=f"Batch edit {len(edits)} cells", edit_type="batch")

    updated = 0
    for edit in edits:
        if edit.col in _state.current_data.columns and 0 <= edit.row < len(_state.current_data):
            _state.current_data.loc[edit.row, edit.col] = edit.value
            updated += 1

    _invalidate_metadata_cache()
    return {"status": "ok", "updated": updated, "total": len(edits)}


# ---------------------------------------------------------------------------
# Row Operations
# ---------------------------------------------------------------------------


@router.post("/row")
async def insert_row(index: int = -1, count: int = 1) -> Dict[str, Any]:
    """Insert one or more empty rows at *index* (default: append at end)."""
    _require_data()
    # Using _state.current_data

    push_undo(description=f"Insert {count} row(s) at index {index}", edit_type="row_insert")

    new_rows = pd.DataFrame({col: [None] * count for col in _state.current_data.columns})
    if index < 0 or index >= len(_state.current_data):
        _state.current_data = pd.concat([_state.current_data, new_rows], ignore_index=True)
    else:
        before = _state.current_data.iloc[:index]
        after = _state.current_data.iloc[index:]
        _state.current_data = pd.concat([before, new_rows, after], ignore_index=True)

    _invalidate_metadata_cache()
    return {"status": "ok", "rows": len(_state.current_data), "inserted": count}


@router.delete("/row/{row_index}")
async def delete_row(row_index: int) -> Dict[str, Any]:
    """Delete a row by index."""
    _require_data()
    # Using _state.current_data

    if row_index < 0 or row_index >= len(_state.current_data):
        raise HTTPException(status_code=400, detail=f"Row index {row_index} out of bounds.")

    push_undo(
        description=f"Delete row {row_index}",
        edit_type="row_delete",
        edit_detail={"index": row_index},
    )

    _state.current_data = _state.current_data.drop(index=row_index).reset_index(drop=True)
    _invalidate_metadata_cache()
    return {"status": "ok", "rows": len(_state.current_data)}


# ---------------------------------------------------------------------------
# Column Operations
# ---------------------------------------------------------------------------


@router.post("/column")
async def add_column(req: AddColumnRequest) -> Dict[str, Any]:
    """Add a new column to the dataset (like SPSS adding a variable)."""
    _require_data()
    # Using _state.current_data

    if req.name in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Column '{req.name}' already exists.")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Column name cannot be empty.")

    push_undo(description=f"Add column '{req.name}'", edit_type="col_add")

    _state.current_data[req.name] = req.default_value
    init_variable_metadata(_state.current_data)
    _invalidate_metadata_cache()
    return {"status": "ok", "column": req.name, "rows": len(_state.current_data), "cols": len(_state.current_data.columns)}


@router.delete("/column/{col_name}")
async def delete_column(col_name: str) -> Dict[str, Any]:
    """Delete a column from the dataset."""
    _require_data()
    # Using _state.current_data

    if col_name not in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Column '{col_name}' not found.")

    push_undo(description=f"Delete column '{col_name}'", edit_type="col_delete")

    _state.current_data = _state.current_data.drop(columns=[col_name])
    init_variable_metadata(_state.current_data)
    _invalidate_metadata_cache()
    return {"status": "ok", "columns": list(_state.current_data.columns)}


# ---------------------------------------------------------------------------
# Variable Metadata (SPSS Variable View)
# ---------------------------------------------------------------------------


@router.get("/variable-view")
async def get_variable_view() -> List[Dict[str, Any]]:
    """Return all variable metadata as a list (SPSS Variable View)."""
    _require_data()
    cols = _build_column_info(_state.current_data)
    return [c.model_dump() for c in cols]


@router.put("/variable")
async def update_variable(req: VariableMetaUpdate) -> Dict[str, Any]:
    """Update metadata for a single variable."""
    _require_data()
    if req.name not in _state.variable_metadata:
        raise HTTPException(status_code=400, detail=f"Variable '{req.name}' not found.")

    push_undo(description=f"Update variable metadata: {req.name}", edit_type="meta")
    success = update_variable_meta(req.name, req.updates)
    _invalidate_metadata_cache()
    return {"status": "ok" if success else "error", "variable": req.name}


@router.put("/value-labels")
async def set_value_labels(req: ValueLabelSet) -> Dict[str, Any]:
    """Set value labels for a variable (e.g. 1=Male, 2=Female)."""
    _require_data()
    if req.column not in _state.variable_metadata:
        raise HTTPException(status_code=400, detail=f"Variable '{req.column}' not found.")

    # Convert keys to the same type as the column
    col_dtype = _state.current_data[req.column].dtype
    typed_labels = {}
    for k, v in req.value_labels.items():
        try:
            if pd.api.types.is_numeric_dtype(col_dtype):
                typed_labels[float(k) if "." in str(k) else int(k)] = v
            else:
                typed_labels[k] = v
        except (ValueError, TypeError):
            typed_labels[k] = v

    _state.variable_metadata[req.column]["value_labels"] = typed_labels
    _invalidate_metadata_cache()
    return {"status": "ok", "column": req.column, "value_labels": typed_labels}


@router.put("/missing-values")
async def set_missing_values(req: MissingValueSet) -> Dict[str, Any]:
    """Set user-defined missing values for a variable."""
    _require_data()
    if req.column not in _state.variable_metadata:
        raise HTTPException(status_code=400, detail=f"Variable '{req.column}' not found.")
    _state.variable_metadata[req.column]["missing_values"] = req.missing_values
    _invalidate_metadata_cache()
    return {"status": "ok", "column": req.column, "missing_values": req.missing_values}


# ---------------------------------------------------------------------------
# Compute Variable
# ---------------------------------------------------------------------------

import ast
import operator
import re
import math
import numpy as np

_SAFE_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.And: lambda a, b: a & b, ast.Or: lambda a, b: a | b,
    ast.Invert: operator.inv,
    ast.Not: operator.not_,
}

_SAFE_FUNCTIONS = {
    "sqrt": np.sqrt, "log": np.log, "log10": np.log10, "log2": np.log2,
    "exp": np.exp, "abs": np.abs, "round": np.round, "ceil": np.ceil,
    "floor": np.floor, "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "mean": np.nanmean, "median": np.nanmedian, "min": np.nanmin,
    "max": np.nanmax, "std": np.nanstd, "var": np.nanvar,
    "sum": np.nansum, "len": len, "str": str, "int": int, "float": float,
}


def _eval_ast(node: ast.AST, df: pd.DataFrame) -> pd.Series:
    """Evaluate an AST node safely against a DataFrame."""
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, df)
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, str):
            return pd.Series(val, index=df.index)
        return pd.Series(val, index=df.index)
    if isinstance(node, ast.Name):
        name = node.id
        if name in df.columns:
            return df[name]
        if name in _SAFE_FUNCTIONS:
            return _SAFE_FUNCTIONS[name]
        raise ValueError(f"Unknown column or function: '{name}'")
    if isinstance(node, ast.Call):
        func = _eval_ast(node.func, df)
        args = [_eval_ast(a, df) for a in node.args]
        if callable(func):
            return func(*args)
        raise ValueError(f"Cannot call non-function: {func}")
    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, df)
        right = _eval_ast(node.right, df)
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand, df)
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(operand)
    if isinstance(node, ast.Compare):
        left = _eval_ast(node.left, df)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_ast(comparator, df)
            op_func = _SAFE_OPERATORS.get(type(op))
            if op_func is None:
                raise ValueError(f"Unsupported comparison: {type(op).__name__}")
            left = op_func(left, right)
        return left
    if isinstance(node, ast.BoolOp):
        left = _eval_ast(node.values[0], df)
        for val in node.values[1:]:
            right = _eval_ast(val, df)
            op_func = _SAFE_OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported boolean op: {type(node.op).__name__}")
            left = op_func(left, right)
        return left
    if isinstance(node, ast.IfExp):
        test = _eval_ast(node.test, df)
        body = _eval_ast(node.body, df)
        orelse = _eval_ast(node.orelse, df)
        return pd.Series(
            np.where(test.astype(bool) if isinstance(test, pd.Series) else test,
                     body.values if isinstance(body, pd.Series) else body,
                     orelse.values if isinstance(orelse, pd.Series) else orelse),
            index=df.index
        )
    if isinstance(node, ast.Attribute):
        value = _eval_ast(node.value, df)
        attr = node.attr
        if hasattr(value, attr):
            return getattr(value, attr)
        raise ValueError(f"Cannot access attribute '{attr}' on {type(value).__name__}")
    if isinstance(node, ast.Subscript):
        value = _eval_ast(node.value, df)
        slice_val = _eval_ast(node.slice, df)
        return value[slice_val]
    if isinstance(node, ast.Slice):
        lower = _eval_ast(node.lower, df) if node.lower else None
        upper = _eval_ast(node.upper, df) if node.upper else None
        step = _eval_ast(node.step, df) if node.step else None
        return slice(lower, upper, step)
    if isinstance(node, ast.List):
        return [_eval_ast(el, df) for el in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_ast(el, df) for el in node.elts)
    if isinstance(node, ast.Dict):
        return {_eval_ast(k, df): _eval_ast(v, df) for k, v in zip(node.keys, node.values)}
    raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def _evaluate_expression(expr: str, df: pd.DataFrame) -> pd.Series:
    """Safely evaluate an expression against a DataFrame using AST-based evaluation."""
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_ast(tree, df)
        if isinstance(result, pd.Series):
            return result
        if np.isscalar(result):
            return pd.Series([result] * len(df), index=df.index)
        raise ValueError(f"Expression returned unsupported type: {type(result)}")
    except SyntaxError as e:
        raise HTTPException(status_code=422, detail=f"Expression syntax error: {e}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Expression error: {e}")


@router.post("/compute")
async def compute_variable(req: ComputeRequest) -> Dict[str, Any]:
    """Create a new variable by evaluating an expression."""
    _require_data()

    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Variable name cannot be empty.")
    if req.name in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Column '{req.name}' already exists.")

    push_undo(description=f"Compute variable '{req.name}'", edit_type="compute")

    try:
        result = _evaluate_expression(req.expression, _state.current_data)
        _state.current_data[req.name] = result.values
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to compute: {exc}")

    init_variable_metadata(_state.current_data)
    _invalidate_metadata_cache()

    return {
        "status": "ok",
        "name": req.name,
        "expression": req.expression,
        "rows": len(_state.current_data),
        "cols": len(_state.current_data.columns),
    }


@router.post("/compute/preview")
async def compute_preview(req: ComputeRequest) -> Dict[str, Any]:
    """Preview the first 10 values of a computed expression."""
    _require_data()

    try:
        result = _evaluate_expression(req.expression, _state.current_data)
        preview_vals = result.head(10).tolist()
        return {
            "status": "ok",
            "expression": req.expression,
            "preview": preview_vals,
            "dtype": str(result.dtype),
            "count": len(result),
            "missing": int(result.isna().sum()),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Preview error: {exc}")


# ---------------------------------------------------------------------------
# Recode
# ---------------------------------------------------------------------------

@router.post("/recode")
async def recode_variable(req: RecodeRequest) -> Dict[str, Any]:
    """Recode values in a column — into same or new column."""
    _require_data()

    if req.column not in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Column '{req.column}' not found.")

    target_col = req.into_new if req.into_new else req.column

    if req.into_new and req.into_new in _state.current_data.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{req.into_new}' already exists.")

    push_undo(description=f"Recode '{req.column}'", edit_type="recode")

    try:
        series = _state.current_data[req.column].copy()

        if req.mappings:
            # Simple old_value -> new_value mapping
            for old_val_str, new_val in req.mappings.items():
                # Try to convert old_val_str to match column dtype
                try:
                    if pd.api.types.is_numeric_dtype(series.dtype):
                        old_val = float(old_val_str) if '.' in old_val_str else int(old_val_str)
                    else:
                        old_val = old_val_str
                except (ValueError, TypeError):
                    old_val = old_val_str
                series = series.replace(old_val, new_val)

        if req.rules:
            # Range-based rules: [{from_val, to_val, new_value}, ...]
            for rule in req.rules:
                from_v = rule.from_val
                to_v = rule.to_val
                new_v = rule.new_value

                if from_v is not None and to_v is not None:
                    mask = (series >= from_v) & (series <= to_v)
                elif from_v is not None:
                    mask = series >= from_v
                elif to_v is not None:
                    mask = series <= to_v
                else:
                    continue

                # Handle NaN in mask
                mask = mask.fillna(False)
                series[mask] = new_v

        _state.current_data[target_col] = series

    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Recode failed: {exc}")

    init_variable_metadata(_state.current_data)
    _invalidate_metadata_cache()

    return {
        "status": "ok",
        "source_column": req.column,
        "target_column": target_col,
        "rows": len(_state.current_data),
    }


# ---------------------------------------------------------------------------
# Undo / Redo
# ---------------------------------------------------------------------------


@router.post("/undo", response_model=UndoRedoResponse)
async def undo_action() -> UndoRedoResponse:
    """Undo the last edit action."""
    _require_data()
    desc = undo()
    info = get_undo_info()
    return UndoRedoResponse(
        success=desc is not None,
        description=desc,
        undo_count=info["undo_count"],
        redo_count=info["redo_count"],
    )


@router.post("/redo", response_model=UndoRedoResponse)
async def redo_action() -> UndoRedoResponse:
    """Redo the last undone action."""
    _require_data()
    desc = redo()
    info = get_undo_info()
    return UndoRedoResponse(
        success=desc is not None,
        description=desc,
        undo_count=info["undo_count"],
        redo_count=info["redo_count"],
    )


@router.get("/undo-info")
async def undo_info() -> Dict[str, Any]:
    """Return undo/redo stack status."""
    return get_undo_info()


# ---------------------------------------------------------------------------
# Survival Data Preparation
# ---------------------------------------------------------------------------


@router.post("/survival-prep", response_model=SurvivalPrepResponse)
async def survival_prep(body: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare survival data from raw date columns.

    Computes survival time and event/censor status from three columns:
    - ``start_col``: date of diagnosis / study entry
    - ``event_col``: date of event (death), may be empty/NaN for censored
    - ``censor_col``: date of last follow-up for censored subjects

    Request body:
        - ``start_col`` (str, required) — date column for time origin
        - ``event_col`` (str, required) — date column for the event
        - ``censor_col`` (str, required) — date column for last follow-up
        - ``unit`` (str, default "months") — "days", "months", or "years"
        - ``new_time_col`` (str, default "survival_time") — output column name
        - ``new_status_col`` (str, default "event_status") — output column name
        - ``event_code`` (int, default 1) — value for event occurred

    Returns:
        dict with ``status``, ``rows``, ``n_events``, ``n_censored``,
        ``mean_time``, ``new_time_col``, ``new_status_col``.
    """
    _require_data()

    start_col = body.get("start_col")
    event_col = body.get("event_col")
    censor_col = body.get("censor_col")

    if not all([start_col, event_col, censor_col]):
        raise HTTPException(
            status_code=400,
            detail="All three of 'start_col', 'event_col', and 'censor_col' are required.",
        )

    for col in [start_col, event_col, censor_col]:
        if col not in _state.current_data.columns:
            raise HTTPException(
                status_code=400, detail=f"Column '{col}' not found in dataset.",
            )

    unit = body.get("unit", "months")
    new_time_col = body.get("new_time_col", "survival_time")
    new_status_col = body.get("new_status_col", "event_status")
    event_code = body.get("event_code", 1)
    dayfirst = body.get("dayfirst", False)  # True for DD/MM/YYYY format

    # Avoid overwriting existing columns
    for col_name in [new_time_col, new_status_col]:
        if col_name in _state.current_data.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{col_name}' already exists. Choose a different output column name.",
            )

    push_undo(description=f"Survival prep: {new_time_col}, {new_status_col}", edit_type="survival_prep")

    df = _state.current_data

    try:
        # Coerce all three columns to datetime
        start_dates = pd.to_datetime(df[start_col], errors="coerce", dayfirst=dayfirst)
        event_dates = pd.to_datetime(df[event_col], errors="coerce", dayfirst=dayfirst)
        censor_dates = pd.to_datetime(df[censor_col], errors="coerce", dayfirst=dayfirst)

        # Count parse successes for diagnostics
        total_rows = len(df)
        event_parsed = int(event_dates.notna().sum())
        censor_parsed = int(censor_dates.notna().sum())
        start_parsed = int(start_dates.notna().sum())

        # Use event date if available, otherwise censor date
        end_dates = event_dates.where(event_dates.notna(), censor_dates)

        # Calculate time delta in days
        delta = (end_dates - start_dates).dt.days

        # Convert to requested unit
        if unit == "days":
            time_values = delta
        elif unit == "years":
            time_values = delta / 365.25
        else:  # months (default)
            time_values = delta / 30.44

        # Round to 2 decimal places
        time_values = time_values.round(2)

        # Create event status: 1 if event date is present, 0 otherwise
        event_status = event_dates.notna().astype(int) * event_code

        # Handle cases where both event and censor are NaN
        # (no usable data — set time to NaN and status to 0)
        no_data_mask = start_dates.isna() | end_dates.isna()
        time_values[no_data_mask] = None
        event_status[no_data_mask] = 0

        # Negative or zero times
        negative_mask = (time_values.notna()) & (time_values <= 0)
        if negative_mask.any():
            n_negative = int(negative_mask.sum())
            time_values[negative_mask] = 0.01  # Minimal positive time

        # Add new columns to dataframe
        df[new_time_col] = time_values
        df[new_status_col] = event_status.astype(float)

    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Survival prep failed: {exc}")

    init_variable_metadata(df)
    _invalidate_metadata_cache()

    n_events = int((df[new_status_col] == event_code).sum())
    n_censored = int(len(df) - n_events)
    valid_times = df[new_time_col].dropna()
    mean_time = round(float(valid_times.mean()), 2) if len(valid_times) > 0 else None

    return {
        "status": "ok",
        "rows": len(df),
        "n_events": n_events,
        "n_censored": n_censored,
        "mean_time": mean_time,
        "new_time_col": new_time_col,
        "new_status_col": new_status_col,
        "unit": unit,
        "diagnostics": {
            "total_rows": total_rows,
            "start_parsed": start_parsed,
            "event_parsed": event_parsed,
            "censor_parsed": censor_parsed,
            "dayfirst": dayfirst,
        },
    }


# ---------------------------------------------------------------------------
# Date Format Detection
# ---------------------------------------------------------------------------


@router.get("/date-format/{col_name}")
async def detect_date_format(col_name: str) -> Dict[str, Any]:
    """Detect the likely date format of a column.

    Samples non-null values and tries parsing with common format strategies.
    Returns the best guess so the frontend can suggest dayfirst or a specific format.

    Returns:
        dict with ``detected`` (str), ``confidence`` (float 0-1),
        ``dayfirst`` (bool), ``sample_count``, ``sample_values``.
    """
    _require_data()

    if col_name not in _state.current_data.columns:
        raise HTTPException(
            status_code=400, detail=f"Column '{col_name}' not found in dataset.",
        )

    series = _state.current_data[col_name].dropna()
    if len(series) == 0:
        return {
            "detected": "unknown",
            "confidence": 0,
            "dayfirst": False,
            "sample_count": 0,
            "sample_values": [],
        }

    # Sample up to 30 values
    sample = series.head(30).astype(str).tolist()
    n = len(sample)

    # Strategy 1: dayfirst=False (MM/DD/YYYY)
    parsed_mdy = pd.to_datetime(pd.Series(sample), errors="coerce", dayfirst=False)
    n_mdy = int(parsed_mdy.notna().sum())

    # Strategy 2: dayfirst=True (DD/MM/YYYY)
    parsed_dmy = pd.to_datetime(pd.Series(sample), errors="coerce", dayfirst=True)
    n_dmy = int(parsed_dmy.notna().sum())

    # Strategy 3: ISO format (already unambiguous)
    parsed_iso = pd.to_datetime(pd.Series(sample), errors="coerce")
    n_iso = int(parsed_iso.notna().sum())

    # Determine best strategy
    best_n = max(n_mdy, n_dmy, n_iso)
    confidence = round(best_n / n, 2) if n > 0 else 0

    if n_dmy > n_mdy and n_dmy >= n_iso:
        detected = "DD/MM/YYYY"
        dayfirst = True
    elif n_mdy > n_dmy and n_mdy >= n_iso:
        detected = "MM/DD/YYYY"
        dayfirst = False
    elif n_iso >= max(n_mdy, n_dmy):
        detected = "YYYY-MM-DD (ISO)"
        dayfirst = False  # ISO is unambiguous
    else:
        detected = "mixed/unknown"
        dayfirst = False

    # Also check if values look like dates at all
    looks_like_date = confidence >= 0.5

    return {
        "detected": detected,
        "confidence": confidence,
        "dayfirst": dayfirst,
        "looks_like_date": looks_like_date,
        "sample_count": n,
        "sample_values": sample[:5],
        "parsed_counts": {
            "mdy": n_mdy,
            "dmy": n_dmy,
            "iso": n_iso,
        },
    }


# ---------------------------------------------------------------------------
# Fix / Standardize Dates
# ---------------------------------------------------------------------------


@router.post("/fix-dates")
async def fix_dates(body: Dict[str, Any]) -> Dict[str, Any]:
    """Standardize dates in a column to YYYY-MM-DD format.

    Handles mixed date formats automatically by trying multiple parse
    strategies per row and picking the one that succeeds.

    Request body:
        - ``column`` (str, required) — column to fix
        - ``dayfirst`` (bool, default False) — preferred parse order

    Returns:
        dict with ``fixed``, ``already_valid``, ``failed`` counts,
        and ``sample_before`` / ``sample_after``.
    """
    _require_data()

    column = body.get("column")
    if not column:
        raise HTTPException(status_code=400, detail="'column' is required.")
    if column not in _state.current_data.columns:
        raise HTTPException(
            status_code=400, detail=f"Column '{column}' not found in dataset.",
        )

    dayfirst = body.get("dayfirst", False)

    push_undo(description=f"Fix dates in '{column}'", edit_type="fix_dates")

    df = _state.current_data
    series = df[column].copy()
    n_total = len(series)

    # Sample before
    non_null = series.dropna()
    sample_before = non_null.head(5).astype(str).tolist()
    already_parsed = pd.to_datetime(non_null, errors="coerce")
    n_already_valid = int(already_parsed.notna().sum())

    # Try both strategies for each value
    def try_parse(val):
        """Try to parse a single value, return formatted date or original."""
        if pd.isna(val):
            return val
        s = str(val).strip()
        if not s:
            return val

        strategies = [
            ("DMY", True),
            ("MDY", False),
        ]
        # Put preferred strategy first
        if dayfirst:
            strategies = [("DMY", True), ("MDY", False)]
        else:
            strategies = [("MDY", False), ("DMY", True)]

        for _name, df_flag in strategies:
            parsed = pd.to_datetime(s, errors="coerce", dayfirst=df_flag)
            if pd.notna(parsed):
                # Validate: if day > 12 and strategy was MDY, this is likely wrong
                # but we trust the parse if it succeeded
                return parsed.strftime("%Y-%m-%d")

        return val  # Could not parse, keep original

    fixed_series = series.apply(try_parse)
    df[column] = fixed_series

    # Count results
    after_parsed = pd.to_datetime(fixed_series.dropna(), errors="coerce")
    n_fixed = int(after_parsed.notna().sum()) - n_already_valid
    if n_fixed < 0:
        n_fixed = 0
    n_failed = n_total - int(after_parsed.notna().sum()) - int(series.isna().sum())

    init_variable_metadata(df)

    sample_after = df[column].dropna().head(5).astype(str).tolist()

    return {
        "status": "ok",
        "column": column,
        "total_rows": n_total,
        "already_valid": n_already_valid,
        "fixed": n_fixed,
        "failed": max(0, n_failed),
        "dayfirst_used": dayfirst,
        "sample_before": sample_before,
        "sample_after": sample_after,
    }


# ── Single-dataset info (replaces multi-dataset list) ─────────────────────


@router.get("/datasets")
async def list_datasets() -> List[Dict[str, Any]]:
    """Return the currently loaded dataset as a single-item list."""
    if _state.current_data is None:
        return []
    return [{
        "id": "default",
        "name": _state.current_filename or "Loaded dataset",
        "rows": len(_state.current_data),
        "cols": len(_state.current_data.columns),
        "active": True,
    }]


@router.get("/{ds_id}/columns")
async def dataset_columns(ds_id: str) -> List[str]:
    """Return column names for a dataset (ignores ID in single-dataset mode)."""
    if _state.current_data is None:
        return []
    return list(_state.current_data.columns)