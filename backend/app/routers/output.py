"""
DevStat — Output Router

Endpoints for generating and exporting statistical output in various
formats (PDF, HTML).  Uses Jinja2 for templating and WeasyPrint for
PDF generation.

Mounted at ``/api/output`` in the main FastAPI application.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

import app.state as _state
from app.state import require_data

router = APIRouter(prefix="", tags=["Output"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_require_data = require_data


# ---------------------------------------------------------------------------
# Output list (stub for output viewer)
# ---------------------------------------------------------------------------


@router.get("/")
async def list_output() -> Dict[str, Any]:
    """Return a list of generated output items."""
    return {"items": [], "count": 0}


@router.delete("/")
async def clear_output() -> Dict[str, Any]:
    """Clear all generated output."""
    return {"status": "ok", "message": "Output cleared."}


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


@router.post("/export/pdf")
async def export_pdf(body: Dict[str, Any]) -> Response:
    """Export analysis results or dataset as a styled PDF document.

    Request body:
        - ``type`` (str): ``"data"`` (entire dataset), ``"results"``
          (analysis results), or ``"summary"`` (basic dataset summary).
        - ``title`` (str, optional): Title for the document.
        - ``content`` (dict, optional): Analysis result data to include.
        - ``columns`` (list of str, optional): Columns to include for
          ``"data"`` type.
        - ``rows`` (int, optional): Max rows for ``"data"`` type (default 100).

    Returns
    -------
    Response
        PDF file as streaming response.
    """
    _require_data()

    output_type = body.get("type", "summary")
    title = body.get("title", "DevStat Report")
    content = body.get("content")
    columns = body.get("columns")
    max_rows = body.get("rows", 100)

    df = _state.current_data

    # Build HTML content.
    html = _build_pdf_html(df, output_type, title, content, columns, max_rows)

    # Generate PDF.
    try:
        import weasyprint
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="weasyprint is not installed. pip install weasyprint",
        )

    try:
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {e}",
        )

    filename = title.replace(" ", "_").lower() + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_pdf_html(
    df,
    output_type: str,
    title: str,
    content: Optional[Dict],
    columns: Optional[List[str]],
    max_rows: int,
) -> str:
    """Build HTML string for PDF export using Jinja2."""
    from jinja2 import Template

    css = """
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; margin: 40px; color: #333; }
        h1 { color: #005eb8; font-size: 20pt; border-bottom: 2px solid #005eb8; padding-bottom: 8px; }
        h2 { color: #333; font-size: 14pt; margin-top: 24px; }
        table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 9pt; }
        th { background-color: #005eb8; color: white; padding: 6px 8px; text-align: left; font-weight: bold; }
        td { padding: 4px 8px; border-bottom: 1px solid #ddd; }
        tr:nth-child(even) { background-color: #f5f8fc; }
        .summary { font-size: 11pt; margin: 16px 0; }
        .footer { margin-top: 40px; font-size: 8pt; color: #999; border-top: 1px solid #ccc; padding-top: 8px; }
    </style>
    """

    if output_type == "data":
        import pandas as pd
        # Dataset table.
        cols = columns if columns else list(df.columns)
        preview = df[cols].head(max_rows)
        rows_html = ""
        for _, row in preview.iterrows():
            cells = "".join(
                f"<td>{row[col] if not pd.isna(row[col]) else ''}</td>"
                for col in cols
            )
            rows_html += f"<tr>{cells}</tr>"

        header_html = "".join(f"<th>{col}</th>" for col in cols)
        table_html = f"<table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>"

        body_html = f"""
        <div class="summary">
            <p><strong>Filename:</strong> {_state.current_filename or 'Untitled'}</p>
            <p><strong>Rows:</strong> {len(df)} | <strong>Columns:</strong> {len(df.columns)}</p>
            <p><strong>Showing:</strong> First {min(max_rows, len(df))} rows of {len(cols)} columns</p>
        </div>
        {table_html}
        """

    elif output_type == "results":
        # Analysis results.
        body_html = _render_results_html(content)

    else:
        # Summary.
        import numpy as np
        import pandas as pd

        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        cat_cols = [c for c in df.columns if c not in num_cols]

        summary_rows = ""
        for col in df.columns:
            dtype = str(df[col].dtype)
            missing = int(df[col].isna().sum())
            missing_pct = round(missing / len(df) * 100, 2) if len(df) > 0 else 0
            unique = int(df[col].nunique())
            if col in num_cols:
                mean_val = round(float(df[col].mean()), 2)
                std_val = round(float(df[col].std()), 2)
                extra = f"Mean: {mean_val}, SD: {std_val}"
            else:
                extra = f"Unique: {unique}"
            summary_rows += f"<tr><td>{col}</td><td>{dtype}</td><td>{missing}</td><td>{missing_pct}%</td><td>{extra}</td></tr>"

        body_html = f"""
        <div class="summary">
            <p><strong>Filename:</strong> {_state.current_filename or 'Untitled'}</p>
            <p><strong>Rows:</strong> {len(df)} | <strong>Columns:</strong> {len(df.columns)}</p>
            <p><strong>Numeric columns:</strong> {len(num_cols)} | <strong>Categorical:</strong> {len(cat_cols)}</p>
        </div>
        <h2>Variable Summary</h2>
        <table>
            <thead><tr><th>Column</th><th>Type</th><th>Missing</th><th>Missing %</th><th>Details</th></tr></thead>
            <tbody>{summary_rows}</tbody>
        </table>
        """

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title>{css}</head>
<body>
<h1>{title}</h1>
{body_html}
<div class="footer">Generated by DevStat Medical Statistics Software</div>
</body>
</html>"""

    return html


def _render_results_html(content: Optional[Dict]) -> str:
    """Render analysis results as HTML."""
    if not content:
        return "<p>No results content provided.</p>"

    import numpy as np
    import pandas as pd

    html_parts = []

    # Test name.
    if content.get("test_name"):
        html_parts.append(f"<h2>{content['test_name']}</h2>")

    # Descriptive stats.
    if content.get("descriptives"):
        html_parts.append("<h3>Descriptives</h3>")
        html_parts.append(_dict_or_table_html(content["descriptives"]))

    # ANOVA table / coefficients.
    for key in ["anova_table", "coefficients", "loadings", "item_stats"]:
        if content.get(key) and isinstance(content[key], list):
            html_parts.append(f"<h3>{key.replace('_', ' ').title()}</h3>")
            html_parts.append(_list_of_dicts_table_html(content[key]))

    # Model summary.
    if content.get("model_summary"):
        html_parts.append("<h3>Model Summary</h3>")
        html_parts.append(_dict_or_table_html(content["model_summary"]))

    # Interpretation.
    if content.get("interpretation"):
        html_parts.append(f"<h3>Interpretation</h3><p>{content['interpretation']}</p>")

    # Other top-level key-value pairs.
    for key, value in content.items():
        if key in ("test_name", "descriptives", "anova_table", "coefficients",
                    "loadings", "item_stats", "model_summary", "interpretation",
                    "variance_explained", "communalities"):
            continue
        if isinstance(value, (str, int, float, bool)):
            html_parts.append(f"<p><strong>{key}:</strong> {value}</p>")

    return "\n".join(html_parts)


def _list_of_dicts_table_html(items: List[Dict]) -> str:
    """Render a list of dicts as an HTML table."""
    if not items:
        return "<p>No data.</p>"

    keys = list(items[0].keys())
    header = "".join(f"<th>{k}</th>" for k in keys)
    rows = ""
    for item in items:
        cells = "".join(f"<td>{item.get(k, '')}</td>" for k in keys)
        rows += f"<tr>{cells}</tr>"

    return f"<table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>"


def _dict_or_table_html(data: Any) -> str:
    """Render a value as HTML — dicts become key-value tables, lists become bullet lists."""
    import numpy as np

    if isinstance(data, dict):
        rows = ""
        for k, v in data.items():
            if isinstance(v, dict):
                v_str = ", ".join(f"{vk}: {vv}" for vk, vv in v.items())
            elif isinstance(v, (list, tuple)):
                v_str = ", ".join(str(x) for x in v[:10])
            else:
                v_str = str(v)
            rows += f"<tr><td><strong>{k}</strong></td><td>{v_str}</td></tr>"
        return f"<table><tbody>{rows}</tbody></table>"
    elif isinstance(data, list):
        items = "".join(f"<li>{_dict_or_table_html(item)}</li>" for item in data[:20])
        return f"<ul>{items}</ul>"
    else:
        return f"<span>{data}</span>"
