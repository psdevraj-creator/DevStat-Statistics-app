"""
DevStat — Transform Router (SPSS Transform Menu)

Endpoints for data transformation operations:
  - Rank Cases       → /api/transform/rank
  - Count Occurrences → /api/transform/count
  - Select If        → /api/transform/select-if
  - Sort Cases       → /api/transform/sort
  - Split File       → /api/transform/split-file
  - Weight Cases     → /api/transform/weight
  - Aggregate Data   → /api/transform/aggregate

Mounted at ``/api/transform`` in the FastAPI application.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

import app.state as _state
from app.models.dataset import (
    AggregateRequest,
    CountRequest,
    RankRequest,
    SelectIfRequest,
    SortRequest,
    SplitFileRequest,
    WeightRequest,
)
from app.state import push_undo, init_variable_metadata, require_data

router = APIRouter(prefix="", tags=["Transform"])


_require_data = require_data


# ---------------------------------------------------------------------------
# Rank Cases (SPSS: Transform → Rank Cases)
# ---------------------------------------------------------------------------


@router.post("/rank")
async def rank_cases(req: RankRequest) -> Dict[str, Any]:
    """Rank cases — create rank variables (rank, rintile, ntile, savage, fractional)."""
    _require_data()
    df = _state.current_data
    new_cols = []

    for var in req.variables:
        if var not in df.columns:
            raise HTTPException(400, detail=f"Column '{var}' not found.")
        series = df[var]
        if not pd.api.types.is_numeric_dtype(series):
            raise HTTPException(400, detail=f"Column '{var}' is not numeric.")

        # Grouping
        if req.group_var and req.group_var in df.columns:
            groups = series.groupby(df[req.group_var], dropna=True)
        else:
            groups = [(None, series)]

        rank_result = pd.Series(index=series.index, dtype=float)
        for _, grp_series in groups:
            idx = grp_series.dropna().index
            if len(idx) == 0:
                continue

            clean = grp_series.dropna()
            if req.descending:
                clean = -clean

            if req.rank_type == "rank":
                ranks = clean.rank(method="average", ascending=True)
            elif req.rank_type == "rintile":
                # Rankit (fractional): (r - 0.5) / n
                r = clean.rank(method="average", ascending=True)
                n = len(clean)
                ranks = (r - 0.5) / n
            elif req.rank_type == "ntile":
                n_tiles = max(2, min(req.ntiles, 100))
                ranks = pd.qcut(clean.rank(method="first"), q=n_tiles,
                                labels=False, duplicates="drop") + 1
            elif req.rank_type == "savage":
                # Savage scores: sum_{i=r}^{n} 1/i
                r = clean.rank(method="average", ascending=True)
                n = len(clean)
                ranks = r.apply(lambda ri: sum(1 / i for i in range(int(ri), n + 1)))
            elif req.rank_type == "fractional":
                # Fractional rank: (r - 1) / (n - 1)
                r = clean.rank(method="average", ascending=True)
                n = len(clean)
                ranks = (r - 1) / (n - 1) if n > 1 else pd.Series([0.5] * n, index=clean.index)
            else:
                raise HTTPException(400, detail=f"Unknown rank type '{req.rank_type}'.")

            rank_result.loc[idx] = ranks.loc[idx]

        col_name = f"{var}{req.suffix}"
        df[col_name] = rank_result
        new_cols.append(col_name)

    push_undo(description=f"Rank: {', '.join(req.variables)}", edit_type="transform")
    init_variable_metadata(df)

    return {"status": "ok", "new_columns": new_cols, "rows": len(df), "cols": len(df.columns)}


# ---------------------------------------------------------------------------
# Count Occurrences (SPSS: Transform → Count Values Within Cases)
# ---------------------------------------------------------------------------


@router.post("/count")
async def count_occurrences(req: CountRequest) -> Dict[str, Any]:
    """Count occurrences of specified values across variables."""
    _require_data()
    df = _state.current_data

    for var in req.variables:
        if var not in df.columns:
            raise HTTPException(400, detail=f"Column '{var}' not found.")

    # Check target column doesn't exist
    if req.target in df.columns:
        raise HTTPException(400, detail=f"Column '{req.target}' already exists.")

    # Convert values to set for matching
    value_set = set(req.values)

    def count_row(row):
        count = 0
        for var in req.variables:
            val = row[var]
            if pd.isna(val):
                continue
            if val in value_set:
                count += 1
            elif isinstance(val, (int, float)) and any(
                isinstance(v, (int, float)) and math.isclose(val, v)
                for v in value_set if isinstance(v, (int, float))
            ):
                count += 1
        return count

    df[req.target] = df.apply(count_row, axis=1)
    push_undo(description=f"Count: {req.target} across {len(req.variables)} vars", edit_type="transform")
    init_variable_metadata(df)

    return {"status": "ok", "column": req.target, "rows": len(df)}


# ---------------------------------------------------------------------------
# Select Cases (SPSS: Data → Select Cases)
# ---------------------------------------------------------------------------


@router.post("/select-if")
async def select_if(req: SelectIfRequest) -> Dict[str, Any]:
    """Filter or delete rows matching an expression."""
    _require_data()
    df = _state.current_data

    # Safe eval for filtering
    allowed_names = {**{c: df[c] for c in df.columns}, "np": np}
    try:
        mask = eval(req.expression, {"__builtins__": {}}, allowed_names)
        if not isinstance(mask, (pd.Series, np.ndarray)):
            mask = pd.Series([bool(mask)] * len(df), index=df.index)
    except Exception as e:
        raise HTTPException(422, detail=f"Expression error: {e}")

    before = len(df)

    if req.mode == "delete":
        push_undo(
            description=f"Delete rows: {req.expression}",
            edit_type="transform",
        )
        _state.current_data = df[~mask].reset_index(drop=True)
        n_deleted = before - len(_state.current_data)
        return {"status": "ok", "mode": "delete", "deleted": n_deleted, "remaining": len(_state.current_data)}

    # Default: filter (hide rows)
    push_undo(
        description=f"Filter: {req.expression}",
        edit_type="transform",
    )
    _state.current_data = df[mask].reset_index(drop=True)
    n_kept = len(_state.current_data)
    return {"status": "ok", "mode": "filter", "kept": n_kept, "removed": before - n_kept}


# ---------------------------------------------------------------------------
# Sort Cases (SPSS: Data → Sort Cases)
# ---------------------------------------------------------------------------


@router.post("/sort")
async def sort_cases(req: SortRequest) -> Dict[str, Any]:
    """Sort cases by one or more key columns."""
    _require_data()
    df = _state.current_data

    if not req.keys:
        raise HTTPException(400, detail="At least one sort key is required.")

    by = []
    ascending = []
    for k in req.keys:
        col = k.get("column", "")
        order = k.get("order", "asc")
        if col not in df.columns:
            raise HTTPException(400, detail=f"Column '{col}' not found.")
        by.append(col)
        ascending.append(order.lower() == "asc")

    push_undo(description=f"Sort by {', '.join(by)}", edit_type="transform")
    _state.current_data = df.sort_values(by=by, ascending=ascending, na_position="last").reset_index(drop=True)

    return {"status": "ok", "sorted_by": by, "rows": len(_state.current_data)}


# ---------------------------------------------------------------------------
# Split File (SPSS: Data → Split File)
# ---------------------------------------------------------------------------


@router.post("/split-file")
async def split_file(req: SplitFileRequest) -> Dict[str, Any]:
    """Set or clear split-file grouping for grouped analysis."""

    if req.state == "off":
        _state._split_var = None
        return {"status": "ok", "state": "off", "message": "Split file disabled."}

    if not req.group_var:
        raise HTTPException(400, detail="group_var required when state is 'on'.")
    if req.group_var not in _state.current_data.columns:
        raise HTTPException(400, detail=f"Column '{req.group_var}' not found.")

    _state._split_var = req.group_var
    return {"status": "ok", "state": req.state, "group_var": req.group_var}


# ---------------------------------------------------------------------------
# Weight Cases (SPSS: Data → Weight Cases)
# ---------------------------------------------------------------------------


@router.post("/weight")
async def weight_cases(req: WeightRequest) -> Dict[str, Any]:
    """Set or clear weight variable for weighted analysis."""

    if req.state == "off":
        _state._weight_var = None
        return {"status": "ok", "state": "off", "message": "Weighting disabled."}

    if not req.weight_var:
        raise HTTPException(400, detail="weight_var required when state is 'on'.")
    if req.weight_var not in _state.current_data.columns:
        raise HTTPException(400, detail=f"Column '{req.weight_var}' not found.")

    _state._weight_var = req.weight_var
    return {"status": "ok", "state": req.state, "weight_var": req.weight_var}


# ---------------------------------------------------------------------------
# Aggregate Data (SPSS: Data → Aggregate)
# ---------------------------------------------------------------------------


_AGG_FUNCTIONS = {
    "mean": "mean",
    "sum": "sum",
    "min": "min",
    "max": "max",
    "std": "std",
    "var": "var",
    "count": "count",
    "first": "first",
    "last": "last",
    "median": "median",
    "nunique": "nunique",
}


@router.post("/aggregate")
async def aggregate_data(req: AggregateRequest) -> Dict[str, Any]:
    """Aggregate data by grouping variable (SPSS AGGREGATE)."""
    _require_data()
    df = _state.current_data

    if req.group_var not in df.columns:
        raise HTTPException(400, detail=f"Group variable '{req.group_var}' not found.")

    agg_dict = {}
    for agg in req.aggregates:
        var = agg.get("variable", "")
        func_name = agg.get("function", "mean")
        if var not in df.columns:
            raise HTTPException(400, detail=f"Variable '{var}' not found.")
        if func_name not in _AGG_FUNCTIONS:
            raise HTTPException(400, detail=f"Unknown aggregate function '{func_name}'.")
        out_name = f"{var}_{func_name}{req.suffix}"
        agg_dict[out_name] = pd.NamedAgg(column=var, aggfunc=_AGG_FUNCTIONS[func_name])

    grouped = df.groupby(req.group_var, dropna=True).agg(**agg_dict).reset_index()
    push_undo(description=f"Aggregate by {req.group_var}", edit_type="transform")

    _state.current_data = grouped
    init_variable_metadata(_state.current_data)

    return {
        "status": "ok",
        "group_var": req.group_var,
        "rows": len(grouped),
        "cols": len(grouped.columns),
        "columns": list(grouped.columns),
    }


# ── Get current transform state ────────────────────────────────────────────


@router.get("/state")
async def transform_state() -> Dict[str, Any]:
    """Return current transform state (split, weight settings)."""
    return {
        "split_var": _state._split_var,
        "weight_var": _state._weight_var,
        "nrows": len(_state.current_data) if _state.current_data is not None else 0,
        "ncols": len(_state.current_data.columns) if _state.current_data is not None else 0,
    }
