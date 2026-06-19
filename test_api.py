"""
DevStat — Automated API Test Script
====================================
Starts a local instance, tests all endpoints, saves chart HTML files,
and prints a pass/fail report.
"""

from __future__ import annotations

import http.cookiejar
import io
import json
import os
import subprocess
import sys
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HOST = "127.0.0.1"
PORT = 15850
BASE = f"http://{HOST}:{PORT}"
DATASET = r"C:\DevStat\test_dataset.csv"
CHART_DIR = Path(r"C:\DevStat\chart_outputs")
CHART_DIR.mkdir(parents=True, exist_ok=True)

passed: List[str] = []
failed: List[str] = []
server_proc: Optional[subprocess.Popen] = None

# Cookie jar so session persists across requests
_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookie_jar)
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _req(method: str, path: str, body: Any = None) -> Tuple[int, Any]:
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with _opener.open(req, timeout=60) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct or not raw:
                return resp.status, json.loads(raw.decode() if raw else "null")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": str(e)}


def _upload(path: str) -> Tuple[int, Any]:
    boundary = str(uuid.uuid4())
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{Path(path).name}"\r\n'.encode()
    )
    body.write(b"Content-Type: application/octet-stream\r\n\r\n")
    with open(path, "rb") as f:
        body.write(f.read())
    body.write(f"\r\n--{boundary}--\r\n".encode())
    data = body.getvalue()

    url = BASE + "/api/data/upload"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with _opener.open(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": str(e)}


def test(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)


def not_fail(name: str, status: int, data: Any, expected_status: int = 200) -> None:
    ok = status == expected_status
    detail = f"status={status}" if not ok else ""
    if ok and isinstance(data, dict) and "error" in data and data["error"]:
        ok = False
        detail = f"error={data['error']}"
    test(name, ok, detail)


_saved_files: List[Tuple[str, str]] = []


def _dict_to_table_html(data: dict, caption: str = "") -> str:
    parts = ["<h3 style='color:#005eb8'>" + caption + "</h3>" if caption else ""]
    rows = ""
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            v_str = json.dumps(v, indent=2, default=str)[:200]
        elif isinstance(v, float):
            v_str = f"{v:.4f}"
        else:
            v_str = str(v)
        rows += f"<tr><td style='font-weight:600;padding:4px 12px;border:1px solid #ddd;background:#f8f9fa'>{k}</td><td style='padding:4px 12px;border:1px solid #ddd'>{v_str}</td></tr>"
    parts.append("<table style='border-collapse:collapse;font-family:monospace;font-size:13px;width:100%'>" + rows + "</table>")
    return "\n".join(parts)


def _list_table_html(data: list, caption: str = "") -> str:
    if not data or not isinstance(data[0], dict):
        return f"<pre style='font-family:monospace;font-size:13px'>{json.dumps(data, indent=2, default=str)[:2000]}</pre>"
    parts = ["<h3 style='color:#005eb8'>" + caption + "</h3>" if caption else ""]
    headers = list(data[0].keys())
    hdr = "".join(f"<th style='background:#005eb8;color:#fff;padding:6px 12px;border:1px solid #005eb8'>{h}</th>" for h in headers)
    rows = ""
    for i, item in enumerate(data[:100]):
        bg = "#f8f9fa" if i % 2 == 0 else "#fff"
        vals = "".join(f"<td style='padding:4px 12px;border:1px solid #ddd'>{json.dumps(item.get(h), default=str)[:80]}</td>" for h in headers)
        rows += f"<tr style='background:{bg}'>{vals}</tr>"
    if len(data) > 100:
        rows += f"<tr><td colspan='{len(headers)}' style='padding:8px;text-align:center;font-style:italic'>… {len(data)-100} more rows</td></tr>"
    parts.append(f"<table style='border-collapse:collapse;font-family:monospace;font-size:13px;width:100%'><thead>{hdr}</thead><tbody>{rows}</tbody></table>")
    return "\n".join(parts)


def save_output(name: str, data: Any, caption: str = ""):
    if not isinstance(data, dict):
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family:'Inter',sans-serif;padding:24px;background:#f1f5f9}}</style></head><body>" + _dict_to_table_html({}, caption) + f"<pre>{json.dumps(data, indent=2, default=str)}</pre></body></html>"
        (CHART_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        _saved_files.append((name, caption or name))
        print(f"  SAVED → {name}.html")
        return

    ct = data.get("chart_type", "")
    _data = data  # we may mutate _data

    # ── Histogram: custom format → Plotly bar + normal curve ─────────────
    if ct == "histogram" and "series" in data:
        traces = []
        colors = ["#005eb8", "#e84343", "#16a34a", "#f59e0b", "#8b5cf6"]
        for i, s in enumerate(data["series"]):
            bins = s.get("bins", [])
            counts = s.get("counts", [])
            centers = [(bins[j] + bins[j + 1]) / 2 for j in range(len(bins) - 1)]
            color = colors[i % len(colors)]
            traces.append({"type": "bar", "x": centers, "y": counts, "name": s.get("group", f"Series {i}"),
                           "marker": {"color": color, "opacity": 0.6}, "width": (bins[2] - bins[1]) * 0.9 if len(bins) > 2 else 1})
            nc = s.get("normal_curve_coords")
            if nc and nc.get("x") and nc.get("y"):
                traces.append({"type": "scatter", "mode": "lines", "x": nc["x"], "y": nc["y"],
                               "name": f"{s.get('group', '')} normal", "line": {"color": color, "width": 2}})
        _data = {"traces": traces, "layout": {"title": f"Histogram: {data.get('column', '')}",
                "xaxis": {"title": data.get("column", "")}, "yaxis": {"title": "Frequency"},
                "bargap": 0.05}}

    # ── Boxplot: custom format → Plotly box traces ──────────────────────
    elif ct == "boxplot" and "groups" in data:
        traces = [{"type": "box", "y": [g["outliers"][0]["value"]] if g.get("outliers") else [],
                    "q1": [g["q1"]], "median": [g["median"]], "q3": [g["q3"]],
                    "lowerfence": [g["min"]], "upperfence": [g["max"]],
                    "name": g.get("group", ""), "boxmean": "sd"} for g in data["groups"]]
        _data = {"traces": traces, "layout": {"title": f"Boxplot: {data.get('column', '')}",
                "yaxis": {"title": data.get("column", "")}}}

    # ── Scatter: custom format → Plotly scatter + regression line ──────
    elif ct == "scatter":
        traces = []
        colors = ["#005eb8", "#e84343", "#16a34a", "#f59e0b", "#8b5cf6"]
        for i, (g, pts) in enumerate(data.get("points", {}).items()):
            color = colors[i % len(colors)]
            traces.append({"type": "scatter", "mode": "markers", "name": str(g),
                           "x": pts.get("x", []), "y": pts.get("y", []), "marker": {"color": color, "size": 5, "opacity": 0.7}})
        rl = data.get("regression_line")
        if rl and rl.get("x") and rl.get("y"):
            traces.append({"type": "scatter", "mode": "lines", "name": f"Regression (R²={data.get('r_squared', 0):.3f})",
                           "x": rl["x"], "y": rl["y"], "line": {"color": "#dc2626", "width": 2}})
        _data = {"traces": traces, "layout": {"title": f"Scatter: {data.get('x_col', '')} vs {data.get('y_col', '')}",
                "xaxis": {"title": data.get("x_col", "")}, "yaxis": {"title": data.get("y_col", "")}}}

    # ── Bar chart: custom format → Plotly bar traces ───────────────────
    elif ct == "bar" and "series" in data:
        traces = []
        for s in data["series"]:
            traces.append({"type": "bar", "x": s.get("categories", []), "y": s.get("values", []),
                           "name": s.get("label", ""), "marker": {"color": "#005eb8"},
                           "error_y": {"type": "data", "array": s.get("errors", []), "visible": True, "color": "#000"}})
        _data = {"traces": traces, "layout": {"title": f"Bar Chart: {data.get('category_col', '')}",
                "xaxis": {"title": data.get("category_col", "")}, "yaxis": {"title": s.get("label", "Count") if data.get("series") else ""}}}

    # ── Violin / QQ: already in Plotly format with traces + layout ─────
    elif "traces" in data and "layout" in data:
        _data = data  # already Plotly-ready

    # ── KM curve: raw series array → Plotly step-line ──────────────────
    elif "series" in data and isinstance(data["series"], list) and any("x" in s for s in data["series"]):
        traces = [{"type": "scatter", "mode": "lines", "name": s.get("group", "All"),
                    "x": s.get("x", []), "y": s.get("y", []), "line": {"shape": "hv"}} for s in data["series"]]
        lr = data.get("log_rank_test", {})
        sub = ""
        if lr and lr.get("p") is not None:
            pv = float(lr['p'])
            p_str = "<0.001" if pv < 0.001 else "{:.4f}".format(pv)
            sub = "Log-rank: chi2 = {:.2f}, p = {}".format(float(lr['statistic']), p_str)
        _data = {"traces": traces, "layout": {"title": {"text": f"Kaplan-Meier Survival Curve<br><span style='font-size:13px;font-weight:normal;color:#64748b'>{sub}</span>"},
                "xaxis": {"title": "Time"}, "yaxis": {"title": "Survival Probability", "range": [0, 1]}}}

    # ── ROC: coordinates array → Plotly ROC curve ──────────────────────
    elif "coordinates" in data and isinstance(data["coordinates"], list):
        coords = data["coordinates"]
        auc = data.get("auc")
        traces = [{"type": "scatter", "mode": "lines", "name": "ROC Curve",
                    "x": [0] + [1 - c.get("fpr", 0) for c in coords] + [1],
                    "y": [0] + [c.get("tpr", 0) for c in coords] + [1], "line": {"shape": "spline"}},
                   {"type": "scatter", "mode": "lines", "name": "Reference", "x": [0, 1], "y": [0, 1],
                    "line": {"dash": "dash", "color": "#94a3b8"}}]
        _data = {"traces": traces, "layout": {"title": f"ROC Curve{'' if auc is None else f' (AUC = {float(auc):.3f})'}",
                "xaxis": {"title": "1 - Specificity"}, "yaxis": {"title": "Sensitivity", "range": [0, 1]}}}

    # ── Forest plot (Cox) ─────────────────────────────────────────────
    elif "coefficients" in data and isinstance(data["coefficients"], list) and any("hr" in c for c in data["coefficients"]):
        coefs = data["coefficients"]
        forest_traces = []
        for c in coefs:
            nm = c.get("name", ""); hr = c.get("hr", 1)
            lo = c.get("hr_ci_lower", c.get("ci_lower", hr * 0.8))
            hi = c.get("hr_ci_upper", c.get("ci_upper", hr * 1.2))
            forest_traces.append({"type": "scatter", "mode": "markers", "name": nm, "y": [nm], "x": [hr],
                                   "marker": {"size": 10, "color": "#005eb8"},
                                   "error_x": {"type": "data", "symmetric": False, "array": [hi - hr], "arrayminus": [hr - lo]}})
        _data = {"traces": forest_traces, "layout": {"title": "Forest Plot (Hazard Ratios)", "xaxis": {"title": "Hazard Ratio", "type": "log"}, "yaxis": {"title": "", "automargin": True}}}

    # Render
    if "traces" in _data and "layout" in _data:
        html = f"""<!DOCTYPE html><html><head><script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script><style>body{{margin:0;background:#f1f5f9}}</style></head><body><div id="chart" style="width:100%;height:100vh"></div><script>
var data = {json.dumps(_data['traces'])}; var layout = {json.dumps(_data['layout'])};
Plotly.newPlot('chart', data, layout, {{responsive: true}});
</script></body></html>"""
    elif "matrix" in _data:
        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family:'Inter',sans-serif;padding:24px;background:#f1f5f9}}</style></head><body>{_dict_to_table_html(_data, caption)}</body></html>"""
    elif isinstance(_data, dict):
        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family:'Inter',sans-serif;padding:24px;background:#f1f5f9}}</style></head><body>{_dict_to_table_html(_data, caption)}</body></html>"""
    else:
        return

    (CHART_DIR / f"{name}.html").write_text(html, encoding="utf-8")
    _saved_files.append((name, caption or name))
    print(f"  SAVED → {name}.html")


def create_report():
    sections: Dict[str, List[Tuple[str, str]]] = {}
    for fname, cap in _saved_files:
        prefix = fname.split("_", 1)[0] if "_" in fname else "99"
        section = {"01": "Charts", "02": "Boxplot", "03": "Scatter", "04": "Bar Chart",
                   "05": "Violin", "06": "Q-Q Plot", "07": "ROC Curve", "08": "KM Curve",
                   "09": "Correlation Heatmap", "10": "Swimmer", "11": "Bland-Altman",
                   "12": "KM Curve", "13": "Forest Plot", "14": "ROC Chart",
                   "20": "Descriptives", "21": "Frequencies", "22": "Crosstabs",
                   "23": "Explore", "24": "Means", "30": "t-test",
                   "31": "Paired t-test", "32": "ANOVA", "33": "Mann-Whitney",
                   "34": "Wilcoxon", "35": "Kruskal-Wallis", "36": "Chi-Square",
                   "37": "Friedman", "38": "Sign Test", "39": "McNemar",
                   "40": "GOF Tests", "41": "Correlation", "42": "Regression",
                   "43": "Survival", "44": "Survival", "45": "Diagnostic",
                   "46": "ROC", "47": "Factor Analysis", "48": "Reliability",
                   "49": "Cluster", "50": "Power", "51": "Power", "52": "Power",
                   "60": "Data", "61": "Variable View"}.get(prefix, "Other")
        sections.setdefault(section, []).append((fname, cap))

    links = ""
    for sec, items in sections.items():
        links += f"<h2 style='color:#003d8b;border-bottom:2px solid #005eb8'>{sec}</h2><ul style='list-style:none;padding:0'>"
        for fn, cap in items:
            links += f'<li style="margin:4px 0"><a href="{fn}.html" style="color:#005eb8;text-decoration:none" target="_blank">▶ {cap}</a></li>'
        links += "</ul>"

    html = f"""<!DOCTYPE html><html><head><title>DevStat Test Report</title>
<style>body{{font-family:'Inter',sans-serif;max-width:800px;margin:0 auto;padding:32px;background:#f1f5f9}}
h1{{color:#003d8b}} .box{{background:#fff;padding:16px;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:24px}}
.pass{{color:#16a34a;font-weight:700}} .fail{{color:#dc2626;font-weight:700}}</style></head>
<body><h1>DevStat Test Report</h1>
<div class='box'><p>Passed: <span class='pass'>{len(passed)}</span> | Failed: <span class='fail'>{len(failed)}</span> | Total: <span>{len(passed)+len(failed)}</span></p>
<p>Saved files: <strong>{len(_saved_files)}</strong></p></div>{links}</body></html>"""
    (CHART_DIR / "report.html").write_text(html, encoding="utf-8")
    print(f"\n  REPORT → report.html ({len(_saved_files)} files)")


# ── 0. Start server ────────────────────────────────────────────────────────


def start_server():
    global server_proc
    print("\n=== Starting DevStat server ===")
    backend_dir = Path(__file__).resolve().parent / "backend"
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
         "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server_proc = proc
    for i in range(60):
        try:
            s, _ = _req("GET", "/api/health")
            if s == 200:
                print(f"  Server ready on port {PORT} (attempt {i+1})")
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Server failed to start within 30 seconds")


def stop_server():
    if server_proc:
        server_proc.terminate()
        server_proc.wait(timeout=5)


# ── 1. Data Upload ─────────────────────────────────────────────────────────


def test_data_upload():
    print("\n── 1. DATA UPLOAD ──")
    s, d = _upload(DATASET)
    not_fail("1.1 Upload CSV", s, d)
    test("1.1b Rows count", d.get("rows") == 120, f"got {d.get('rows')}")
    test("1.1c Cols count", d.get("cols") == 28, f"got {d.get('cols')}")

    s, d = _req("GET", "/api/data/info")
    not_fail("1.2 Dataset info", s, d)
    test("1.2b Rows", d.get("rows") == 120)
    test("1.2c Cols", d.get("cols") == 28)

    s, d = _req("GET", "/api/data/datasets")
    not_fail("1.3 Datasets list", s, d)
    test("1.3b Has dataset", len(d) == 1)

    # Invalid file upload
    import tempfile
    bad = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
    bad.write("hello")
    bad.close()
    s, d = _upload(bad.name)
    not_fail("1.4 Invalid file rejected", s, d, 400)
    os.unlink(bad.name)

    s, d = _req("GET", "/api/data/columns")
    not_fail("1.5 Columns metadata", s, d)
    col_names = [c["name"] for c in d]
    test("1.5b Has age", "age" in col_names)
    test("1.5c Has gender", "gender" in col_names)
    test("1.5d Has outcome", "outcome" in col_names)

    s, d = _req("GET", "/api/data/preview?n=10")
    not_fail("1.6 Preview", s, d)
    test("1.6b Preview rows", isinstance(d, list) and len(d) <= 10, f"got {len(d)}")


# ── 2. Data View ────────────────────────────────────────────────────────────


def test_data_view():
    print("\n── 2. DATA VIEW ──")
    s, d = _req("POST", "/api/data/rows", {"page": 0, "pageSize": 50})
    not_fail("2.1 Paginated rows", s, d)
    test("2.1b Rows returned", len(d.get("rows", [])) <= 50)
    test("2.1c Total", d.get("total") == 120)

    s, d = _req("POST", "/api/data/rows", {
        "page": 0, "pageSize": 20,
        "sortModel": [{"colId": "age", "sort": "desc"}],
    })
    not_fail("2.2 Sort descending", s, d)
    if d.get("rows"):
        test("2.2b First age >= last age", d["rows"][0]["age"] >= d["rows"][-1]["age"])

    s, d = _req("POST", "/api/data/rows", {
        "page": 0, "pageSize": 100,
        "filterModel": {"gender": {"filterType": "text", "type": "equals", "filter": "Female"}},
    })
    not_fail("2.3 Filter gender", s, d)
    if d.get("rows"):
        test("2.3b All filtered", all(r["gender"] == "Female" for r in d["rows"]))

    # Edit cell
    s, d = _req("PUT", "/api/data/cell", {"row": 0, "col": "age", "value": 99})
    not_fail("2.4 Edit cell", s, d)
    test("2.4b Updated value", d.get("age") == 99)

    # Undo
    s, d = _req("POST", "/api/data/undo")
    not_fail("2.5 Undo", s, d)
    test("2.5b Undo success", d.get("success") is True)

    # Redo
    s, d = _req("POST", "/api/data/redo")
    not_fail("2.6 Redo", s, d)
    test("2.6b Redo success", d.get("success") is True)

    # Undo again to restore clean state
    _req("POST", "/api/data/undo")

    # Insert row
    s, d = _req("POST", "/api/data/row?index=-1&count=1")
    not_fail("2.7 Insert row", s, d)
    test("2.7b Row count after insert", d.get("rows") == 121)

    # Delete row
    s, d = _req("DELETE", "/api/data/row/120")
    not_fail("2.8 Delete row", s, d)
    test("2.8b Row count after delete", d.get("rows") == 120)

    # Add column
    s, d = _req("POST", "/api/data/column", {"name": "test_col", "dtype": "numeric"})
    not_fail("2.9 Add column", s, d)

    # Delete column
    s, d = _req("DELETE", "/api/data/column/test_col")
    not_fail("2.10 Delete column", s, d)

    # Batch edit
    s, d = _req("PUT", "/api/data/cells/batch", [
        {"row": 0, "col": "age", "value": 50},
        {"row": 1, "col": "age", "value": 51},
    ])
    not_fail("2.11 Batch edit", s, d)

    # Undo batch
    _req("POST", "/api/data/undo")


# ── 3. Variable View ───────────────────────────────────────────────────────


def test_variable_view():
    print("\n── 3. VARIABLE VIEW ──")
    s, d = _req("GET", "/api/data/variable-view")
    not_fail("3.1 Variable view", s, d)
    test("3.1b Has entries", isinstance(d, list) and len(d) > 0, f"got {len(d)}")

    # Update variable metadata
    s, d = _req("PUT", "/api/data/variable", {
        "name": "age", "updates": {"label": "Patient age at admission (years)"},
    })
    not_fail("3.2 Variable label", s, d)

    # Check label persisted
    s, d = _req("GET", "/api/data/variable-view")
    age_meta = next((x for x in d if x["name"] == "age"), {})
    test("3.3 Label persisted", age_meta.get("label") == "Patient age at admission (years)")

    # Value labels
    s, d = _req("PUT", "/api/data/value-labels", {
        "column": "gender",
        "value_labels": {"1": "Male", "2": "Female"},
    })
    not_fail("3.4 Value labels set", s, d)

    # Missing values
    s, d = _req("PUT", "/api/data/missing-values", {
        "column": "bmi",
        "missing_values": [99, 999],
    })
    not_fail("3.5 Missing values set", s, d)


# ── 4. Transform ────────────────────────────────────────────────────────────


def test_transform():
    print("\n── 4. TRANSFORM ──")
    s, d = _req("POST", "/api/data/compute", {"name": "bmi_ratio", "expression": "bmi / 10"})
    not_fail("4.1 Compute variable", s, d)
    test("4.1b Col created", "bmi_ratio" in (d.get("columns") or [d.get("name", "")]))

    s, d = _req("POST", "/api/data/compute/preview", {
        "name": "preview_test", "expression": "age * 2",
    })
    not_fail("4.2 Compute preview", s, d)
    test("4.2b Has preview", "preview" in d)

    s, d = _req("POST", "/api/data/recode", {
        "column": "pain_score", "into_new": "pain_cat",
        "mappings": {"0": "None", "1": "Mild", "2": "Mild", "3": "Moderate",
                     "4": "Moderate", "5": "Severe"},
    })
    not_fail("4.3 Recode", s, d)
    test("4.3b Column created", d.get("target_column") == "pain_cat")

    s, d = _req("POST", "/api/data/recode", {
        "column": "age", "into_new": "age_group",
        "mappings": {"18-40": "Young", "41-60": "Middle", "61+": "Senior"},
    })
    not_fail("4.4 Recode with mappings", s, d)

    s, d = _req("POST", "/api/transform/rank", {
        "variables": ["bmi"], "rank_type": "rank", "suffix": "_rank",
    })
    not_fail("4.5 Rank cases", s, d)
    test("4.5b New cols", len(d.get("new_columns", [])) > 0)

    s, d = _req("POST", "/api/transform/rank", {
        "variables": ["bmi"], "rank_type": "ntile", "suffix": "_qtile", "ntiles": 4,
    })
    not_fail("4.6 Rank NTile", s, d)

    s, d = _req("POST", "/api/transform/count", {
        "variables": ["smoking_status"], "target": "is_smoker", "values": ["Smoker"],
    })
    not_fail("4.7 Count occurrences", s, d)

    s, d = _req("POST", "/api/transform/sort", {
        "keys": [{"column": "age", "order": "asc"}, {"column": "bmi", "order": "desc"}],
    })
    not_fail("4.8 Sort cases", s, d)

    s, d = _req("POST", "/api/transform/split-file", {
        "state": "on", "group_var": "gender",
    })
    not_fail("4.9 Split file", s, d)
    _req("POST", "/api/transform/split-file", {"state": "off"})

    s, d = _req("POST", "/api/transform/weight", {
        "state": "on", "weight_var": "bmi",
    })
    not_fail("4.10 Weight cases", s, d)
    _req("POST", "/api/transform/weight", {"state": "off"})


# ── 5. Descriptive Statistics ──────────────────────────────────────────────


def test_descriptive():
    print("\n── 5. DESCRIPTIVE ──")
    s, d = _req("POST", "/api/analysis/descriptive", {
        "columns": ["age", "bmi", "cholesterol"],
    })
    not_fail("5.1 Descriptives", s, d)
    test("5.1b Has results", isinstance(d, dict) and len(d) > 0)
    if s == 200:
        save_output("20_descriptives", d, "Descriptive Statistics")

    s, d = _req("POST", "/api/analysis/frequencies", {"column": "smoking_status"})
    not_fail("5.2 Frequencies", s, d)
    test("5.2b Has frequency table", "frequency" in d or "table" in d or any(
        k for k in d if "freq" in k.lower()), f"keys={list(d.keys())}")
    if s == 200:
        save_output("21_frequencies", d, "Frequencies - Smoking Status")

    s, d = _req("POST", "/api/analysis/crosstab", {"row": "gender", "col": "smoking_status"})
    not_fail("5.3 Crosstabs", s, d)
    if s == 200:
        save_output("22_crosstabs", d, "Crosstabs - Gender × Smoking Status")

    s, d = _req("POST", "/api/analysis/explore", {"column": "bmi"})
    not_fail("5.4 Explore", s, d)
    if s == 200:
        save_output("23_explore", d, "Explore - BMI")

    s, d = _req("POST", "/api/analysis/means", {"dependent": "systolic_bp", "group": "treatment_group"})
    not_fail("5.5 Means", s, d)
    if s == 200:
        save_output("24_means", d, "Means - SBP by Treatment Group")


# ── 6. Compare Means ───────────────────────────────────────────────────────


def test_compare_means():
    print("\n── 6. COMPARE MEANS ──")
    s, d = _req("POST", "/api/analysis/ttest", {
        "dependent": ["bmi"], "group": "gender", "test_type": "independent",
    })
    not_fail("6.1 Independent t-test", s, d)
    if s == 200: save_output("30_ttest_independent", d, "Independent t-test - BMI by Gender")

    s, d = _req("POST", "/api/analysis/ttest-paired", {
        "variable1": "systolic_bp", "variable2": "diastolic_bp",
    })
    not_fail("6.2 Paired t-test", s, d)
    if s == 200: save_output("31_ttest_paired", d, "Paired t-test - SBP vs DBP")

    s, d = _req("POST", "/api/analysis/anova", {
        "dependent": ["cholesterol"], "group": "treatment_group", "test_type": "anova",
    })
    not_fail("6.3 One-way ANOVA", s, d)
    if s == 200: save_output("32_anova", d, "One-way ANOVA - Cholesterol by Treatment")

    s, d = _req("POST", "/api/analysis/np-mannwhitney", {
        "dependent": "pain_score", "group": "gender",
    })
    not_fail("6.4 Mann-Whitney U", s, d)
    if s == 200: save_output("33_mannwhitney", d, "Mann-Whitney U - Pain Score by Gender")

    s, d = _req("POST", "/api/analysis/np-wilcoxon", {
        "variable1": "age", "variable2": "bmi",
    })
    not_fail("6.5 Wilcoxon", s, d)
    if s == 200: save_output("34_wilcoxon", d, "Wilcoxon Signed-Rank - Age vs BMI")

    s, d = _req("POST", "/api/analysis/np-kruskalwallis", {
        "dependent": "quality_of_life", "group": "exercise_freq",
    })
    not_fail("6.6 Kruskal-Wallis", s, d)
    if s == 200: save_output("35_kruskal_wallis", d, "Kruskal-Wallis - QoL by Exercise Frequency")

    s, d = _req("POST", "/api/analysis/chisquare", {"row": "gender", "col": "smoking_status"})
    not_fail("6.7 Chi-square", s, d)
    if s == 200: save_output("36_chisquare", d, "Chi-Square - Gender × Smoking")

    s, d = _req("POST", "/api/analysis/np-friedman", {
        "variables": ["anxiety_score", "depression_score", "pain_score"],
    })
    not_fail("6.8 Friedman", s, d)
    if s == 200: save_output("37_friedman", d, "Friedman Test - Anxiety/Depression/Pain")

    s, d = _req("POST", "/api/analysis/np-chisquare", {"column": "gender"})
    not_fail("6.9 Chi-square GOF", s, d)
    if s == 200: save_output("38_chisquare_gof", d, "Chi-Square Goodness-of-Fit - Gender")

    s, d = _req("POST", "/api/analysis/np-binomial", {"column": "gender", "test_proportion": 0.5})
    not_fail("6.10 Binomial", s, d)
    if s == 200: save_output("39_binomial", d, "Binomial Test - Gender")

    s, d = _req("POST", "/api/analysis/np-runs", {"column": "age"})
    not_fail("6.11 Runs test", s, d)
    if s == 200: save_output("40_runs_test", d, "Runs Test - Age")

    s, d = _req("POST", "/api/analysis/np-ks", {"column": "bmi"})
    not_fail("6.12 KS test", s, d)
    if s == 200: save_output("40_ks_test", d, "Kolmogorov-Smirnov Test - BMI")


# ── 7. Correlation ─────────────────────────────────────────────────────────


def test_correlation():
    print("\n── 7. CORRELATION ──")
    cols = ["age", "bmi", "systolic_bp", "cholesterol"]
    s, d = _req("POST", "/api/analysis/correlation", {"columns": cols, "method": "pearson"})
    not_fail("7.1 Pearson correlation", s, d)
    test("7.1b Has correlation matrix", isinstance(d, dict) and "matrix" in d, f"keys={list(d.keys())[:5]}")
    if s == 200: save_output("41_correlation_pearson", d, "Pearson Correlation Matrix")

    s, d = _req("POST", "/api/analysis/correlation", {"columns": cols, "method": "spearman"})
    not_fail("7.2 Spearman correlation", s, d)
    if s == 200: save_output("41_correlation_spearman", d, "Spearman Correlation Matrix")

    s, d = _req("POST", "/api/analysis/partial-correlation", {
        "columns": ["age", "systolic_bp"], "control": ["bmi"],
    })
    not_fail("7.3 Partial correlation", s, d)
    if s == 200: save_output("41_partial_correlation", d, "Partial Correlation - Age×SBP controlling for BMI")


# ── 8. Regression ──────────────────────────────────────────────────────────


def test_regression():
    print("\n── 8. REGRESSION ──")
    s, d = _req("POST", "/api/analysis/linear-regression", {
        "dependent": "systolic_bp", "independents": ["age", "bmi", "cholesterol"],
    })
    not_fail("8.1 Linear regression", s, d)
    test("8.1b Has coefficients", "coefficients" in d or "coef" in d or any(
        k for k in d if "coef" in k.lower()), f"keys={list(d.keys())[:5]}")
    if s == 200: save_output("42_linear_regression", d, "Linear Regression - SBP ~ Age + BMI + Cholesterol")

    s, d = _req("POST", "/api/data/compute", {"name": "diabetes_bin", "expression": "(diabetes == 'Yes') * 1"})
    if s == 200 and not d.get("error"):
        s, d = _req("POST", "/api/analysis/logistic-regression", {
            "dependent": "diabetes_bin", "independents": ["age", "bmi", "cholesterol"],
        })
    not_fail("8.2 Logistic regression", s, d)
    if s == 200: save_output("42_logistic_regression", d, "Logistic Regression - Diabetes ~ Age + BMI + Cholesterol")


# ── 9. Survival ────────────────────────────────────────────────────────────


def test_survival():
    print("\n── 9. SURVIVAL ──")
    s, d = _req("POST", "/api/analysis/kaplan-meier", {
        "time_col": "followup_months", "status_col": "event_occurred",
    })
    not_fail("9.1 Kaplan-Meier", s, d)
    test("9.1b Has survival data", "series" in d or "table" in d or "median" in d or any(
        k for k in d if "survival" in k.lower() or "median" in k.lower()),
         f"keys={list(d.keys())[:5]}")
    if s == 200: save_output("43_kaplan_meier", d, "Kaplan-Meier Survival Curve")

    s, d = _req("POST", "/api/analysis/kaplan-meier", {
        "time_col": "followup_months", "status_col": "event_occurred",
        "factors": ["gender"],
    })
    not_fail("9.2 KM by group", s, d)
    if s == 200: save_output("12_km_curve_by_gender", d, "KM Curve by Gender")

    s, d = _req("POST", "/api/analysis/cox-regression", {
        "time_col": "followup_months", "status_col": "event_occurred",
        "covariates": ["age", "bmi"],
    })
    not_fail("9.3 Cox regression", s, d)
    test("9.3b Has HR", "coefficients" in d or "hr" in str(d.get("coefficients", [])) or
         any(k for k in d if "coef" in k.lower()),
         f"keys={list(d.keys())[:5]}")
    if s == 200: save_output("43_cox_regression", d, "Cox Regression - Age + BMI")

    # KM curve through chart endpoint (also save as chart view)
    s, d = _req("POST", "/api/charts/km-curve", {
        "time_col": "followup_months", "status_col": "event_occurred", "group_col": "gender",
    })
    if s == 200: save_output("08_km_curve_chart", d, "KM Curve (Chart Endpoint)")


# ── 10. Diagnostic ─────────────────────────────────────────────────────────


def test_diagnostic():
    print("\n── 10. DIAGNOSTIC ──")
    s, d = _req("POST", "/api/analysis/diagnostic", {
        "test_col": "pain_score", "gold_col": "event_occurred",
    })
    not_fail("10.1 Diagnostic test", s, d)
    if s == 200: save_output("45_diagnostic", d, "Diagnostic Test - Pain Score vs Event")

    s, d = _req("POST", "/api/analysis/roc", {
        "test_col": "age", "gold_col": "event_occurred",
    })
    not_fail("10.2 ROC analysis", s, d)
    test("10.2b Has AUC", "auc" in d or "roc" in str(list(d.keys())))
    if s == 200: save_output("46_roc_analysis", d, "ROC Analysis - Age predicting Event")

    # ROC curve through chart endpoint
    s, d = _req("POST", "/api/charts/roc-curve", {"test_col": "age", "gold_col": "event_occurred"})
    if s == 200: save_output("14_roc_chart", d, "ROC Curve (Chart Endpoint)")


# ── 11. Factor / Reliability / Cluster / Power ────────────────────────────


def test_advanced():
    print("\n── 11. ADVANCED ──")
    cols = ["age", "bmi", "systolic_bp", "cholesterol", "hemoglobin", "creatinine"]
    s, d = _req("POST", "/api/analysis/factor", {
        "columns": cols, "n_factors": 2, "rotation": "varimax",
    })
    not_fail("11.1 Factor analysis", s, d)
    if s == 200: save_output("47_factor_analysis", d, "Factor Analysis (2 factors)")

    cols2 = ["anxiety_score", "depression_score", "pain_score"]
    s, d = _req("POST", "/api/analysis/reliability", {"columns": cols2})
    not_fail("11.2 Reliability", s, d)
    if s == 200: save_output("48_reliability", d, "Reliability Analysis (Cronbach's Alpha)")

    cols3 = ["age", "bmi", "systolic_bp", "cholesterol"]
    s, d = _req("POST", "/api/analysis/cluster", {
        "columns": cols3, "method": "kmeans", "n_clusters": 3,
    })
    not_fail("11.3 Cluster k-means", s, d)
    if s == 200: save_output("49_cluster", d, "K-Means Cluster Analysis (3 clusters)")

    s, d = _req("POST", "/api/analysis/power", {
        "test": "ttest", "effect_size": 0.5, "power": 0.8, "alpha": 0.05,
    })
    not_fail("11.4 Power t-test", s, d)
    test("11.4b Has sample size", "n" in str(d) or "sample_size" in str(d) or "N" in str(d))
    if s == 200: save_output("50_power_ttest", d, "Power Analysis - Independent t-test")

    s, d = _req("POST", "/api/analysis/power", {
        "test": "anova", "effect_size": 0.25, "power": 0.8, "alpha": 0.05, "k": 3,
    })
    not_fail("11.5 Power ANOVA", s, d)
    if s == 200: save_output("51_power_anova", d, "Power Analysis - ANOVA (3 groups)")

    s, d = _req("POST", "/api/analysis/power", {
        "test": "correlation", "effect_size": 0.3, "power": 0.8, "alpha": 0.05,
    })
    not_fail("11.6 Power correlation", s, d)
    if s == 200: save_output("52_power_correlation", d, "Power Analysis - Pearson Correlation")


# ── 12. Charts ─────────────────────────────────────────────────────────────


def test_charts():
    print("\n── 12. CHARTS ──")
    # Re-upload fresh data so charts use clean dataset
    _upload(DATASET)
    # Re-compute diabetes_bin needed for chart tests
    _req("POST", "/api/data/compute", {"name": "diabetes_bin", "expression": "(diabetes == 'Yes') * 1"})
    tests = [
        ("01_histogram", "POST", "/api/charts/histogram", {"column": "age", "bins": 15}),
        ("02_boxplot", "POST", "/api/charts/boxplot", {"column": "bmi", "group_col": "gender"}),
        ("03_scatter", "POST", "/api/charts/scatter", {"x_col": "age", "y_col": "systolic_bp"}),
        ("04_bar_chart", "POST", "/api/charts/bar", {"category_col": "smoking_status"}),
        ("05_violin", "POST", "/api/charts/violin", {"column": "quality_of_life", "group_col": "exercise_freq"}),
        ("06_qq_plot", "POST", "/api/charts/qq", {"column": "bmi", "dist": "norm"}),
        ("07_roc_curve", "POST", "/api/charts/roc-curve", {"test_col": "age", "gold_col": "event_occurred"}),
        ("08_km_curve", "POST", "/api/charts/km-curve",
         {"time_col": "followup_months", "status_col": "event_occurred", "group_col": "gender"}),
    ]

    for name, method, path, body in tests:
        s, d = _req(method, path, body)
        not_fail(f"12.{tests.index((name,method,path,body))+1} {name}", s, d)
        if s == 200 and "error" in str(d):
            print(f"       (dbg: error={d.get('error','')})")
        if s == 200:
            save_output(name, d, name)

    s, d = _req("POST", "/api/charts/correlation-heatmap", {
        "columns": ["age", "bmi", "systolic_bp", "cholesterol", "hemoglobin"],
        "method": "pearson",
    })
    not_fail("12.9 correlation_heatmap", s, d)
    if s == 200:
        save_output("09_correlation_heatmap", d, "Correlation Heatmap")

    s, d = _req("POST", "/api/charts/swimmer", {
        "patient_col": "patient_id", "start_col": "admission_date",
        "end_col": "discharge_date", "response_col": "outcome",
    })
    not_fail("12.10 swimmer", s, d)
    if s == 200:
        save_output("10_swimmer", d, "Swimmer Plot")

    s, d = _req("POST", "/api/charts/bland-altman", {"col1": "systolic_bp", "col2": "diastolic_bp"})
    not_fail("12.11 bland_altman", s, d)
    if s == 200:
        save_output("11_bland_altman", d, "Bland-Altman Plot")

    # Additional chart: forest plot via analysis endpoint
    s, d = _req("POST", "/api/analysis/cox-forest", {
        "coefficients": [{"name": "Age", "hr": 1.05, "hr_ci_lower": 1.01, "hr_ci_upper": 1.09, "p": 0.012},
                          {"name": "BMI", "hr": 1.12, "hr_ci_lower": 1.03, "hr_ci_upper": 1.22, "p": 0.008},
                          {"name": "Smoker", "hr": 1.85, "hr_ci_lower": 1.25, "hr_ci_upper": 2.74, "p": 0.002}],
    })
    not_fail("12.12 forest_plot", s, d)
    if s == 200:
        save_output("13_forest_plot", d, "Forest Plot (Hazard Ratios)")


# ── 13. Output & Export ────────────────────────────────────────────────────


def test_output():
    print("\n── 13. OUTPUT ──")
    # Reset to get fresh data after all the transforms
    _req("GET", "/api/data/reset")
    _upload(DATASET)

    s, d = _req("GET", "/api/output/")
    not_fail("13.1 Output list", s, d)

    s, r = _req("GET", "/api/data/download")
    test("13.2 Download CSV", s == 200 and isinstance(r, bytes), f"status={s} type={type(r).__name__}")

    s, r = _req("POST", "/api/data/download/excel", {"columns": ["age", "bmi", "gender"]})
    test("13.3 Download Excel", s == 200 and isinstance(r, bytes), f"status={s} type={type(r).__name__}")


# ── Report ─────────────────────────────────────────────────────────────────


def print_report():
    total = len(passed) + len(failed)
    print("\n" + "=" * 55)
    print("DEVSTAT API TEST REPORT")
    print("=" * 55)
    print(f"  PASSED:  {len(passed)}/{total}")
    print(f"  FAILED:  {len(failed)}/{total}")
    if failed:
        print("\n  FAILED TESTS:")
        for f in failed:
            print(f"    ☐ {f}")
    print(f"\n  Saved files: {len(_saved_files)} HTML files → {CHART_DIR}")
    print("  Open report.html for the complete index.")
    print("=" * 55)
    return len(failed) == 0


# ── Main ───────────────────────────────────────────────────────────────────


def main():
    try:
        start_server()
        test_data_upload()
        test_data_view()
        test_variable_view()
        test_transform()
        test_descriptive()
        test_compare_means()
        test_correlation()
        test_regression()
        test_survival()
        test_diagnostic()
        test_advanced()
        test_charts()
        test_output()
        create_report()
        ok = print_report()
        sys.exit(0 if ok else 1)
    finally:
        stop_server()


if __name__ == "__main__":
    main()
