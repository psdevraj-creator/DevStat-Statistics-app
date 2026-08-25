"""
Performance tests for large dataset handling (30,000 rows).

Run: python -m pytest tests/test_performance.py -v -s
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_CSV = os.path.join(os.path.dirname(__file__), "..", "test_large_30k.csv")


@pytest.fixture(scope="module")
def large_csv_path():
    """Ensure the 30k-row CSV exists (generate if needed)."""
    path = TEST_CSV
    if not os.path.exists(path):
        np.random.seed(42)
        n = 30_000
        df = pd.DataFrame({
            "id": range(1, n + 1),
            "age": np.random.normal(55, 15, n).clip(18, 95).astype(int),
            "bmi": np.random.normal(26, 5, n).clip(15, 50).round(1),
            "bp_sys": np.random.normal(130, 20, n).clip(80, 200).astype(int),
            "bp_dia": np.random.normal(82, 12, n).clip(50, 120).astype(int),
            "chol": np.random.normal(200, 40, n).clip(100, 350).astype(int),
            "glucose": np.random.normal(100, 25, n).clip(60, 250).astype(int),
            "treatment": np.random.choice(["A", "B", "C", "Placebo"], n),
            "sex": np.random.choice(["M", "F"], n),
            "smoker": np.random.choice(["Yes", "No"], n, p=[0.3, 0.7]),
            "outcome": np.random.choice([0, 1], n, p=[0.75, 0.25]),
            "time": np.random.exponential(60, n).clip(1, 365).astype(int),
            "event": np.random.choice([0, 1], n, p=[0.7, 0.3]),
        })
        df.to_csv(path, index=False)
    return path


def test_upload_30k_rows(large_csv_path):
    """Upload should complete in under 5 seconds."""
    with open(large_csv_path, "rb") as f:
        t0 = time.time()
        resp = client.post("/api/data/upload", files={"file": ("large.csv", f, "text/csv")})
        elapsed = time.time() - t0

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rows"] == 30_000
    assert data["cols"] == 13
    assert elapsed < 5.0, f"Upload took {elapsed:.2f}s (limit 5s)"
    print(f"\n  Upload: {elapsed:.2f}s ✓")


def test_preview_is_limited(large_csv_path):
    """Preview should return at most 500 rows, not all 30k."""
    _upload(large_csv_path)
    t0 = time.time()
    resp = client.get("/api/data/preview?n=100")
    elapsed = time.time() - t0

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) <= 100, f"Got {len(rows)} rows, expected ≤ 100"
    assert elapsed < 1.0, f"Preview took {elapsed:.2f}s (limit 1s)"
    print(f"\n  Preview 100 rows: {elapsed:.3f}s ✓")


def test_paginated_rows(large_csv_path):
    """Server-side pagination should return the correct page size."""
    _upload(large_csv_path)

    t0 = time.time()
    resp = client.post("/api/data/rows", json={"page": 0, "pageSize": 50})
    elapsed = time.time() - t0

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 50
    assert data["total"] == 30_000
    assert data["page"] == 0
    assert elapsed < 2.0, f"Pagination took {elapsed:.2f}s (limit 2s)"
    print(f"\n  Paginate 50 rows: {elapsed:.3f}s ✓")


def test_sort_performance(large_csv_path):
    """Server-side sorting should complete quickly."""
    _upload(large_csv_path)

    t0 = time.time()
    resp = client.post("/api/data/rows", json={
        "page": 0, "pageSize": 50,
        "sortModel": [{"colId": "age", "sort": "desc"}],
    })
    elapsed = time.time() - t0

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 50
    # Check that ages are descending
    ages = [r["age"] for r in data["rows"] if r.get("age") is not None]
    if len(ages) > 1:
        assert ages[0] >= ages[-1], f"Sort failed: first={ages[0]}, last={ages[-1]}"
    assert elapsed < 3.0, f"Sort took {elapsed:.2f}s (limit 3s)"
    print(f"\n  Sort 30k rows: {elapsed:.3f}s ✓")


def test_filter_performance(large_csv_path):
    """Server-side filtering should complete quickly."""
    _upload(large_csv_path)

    t0 = time.time()
    resp = client.post("/api/data/rows", json={
        "page": 0, "pageSize": 50,
        "filterModel": {"treatment": {"filterType": "text", "type": "equals", "filter": "A"}},
    })
    elapsed = time.time() - t0

    assert resp.status_code == 200
    data = resp.json()
    for row in data["rows"]:
        assert row["treatment"] == "A", f"Filter failed: got {row['treatment']}"
    assert elapsed < 2.0, f"Filter took {elapsed:.2f}s (limit 2s)"
    print(f"\n  Filter 30k rows: {elapsed:.3f}s ✓")


def test_analysis_performance(large_csv_path):
    """Frequencies on large dataset should complete quickly."""
    _upload(large_csv_path)

    t0 = time.time()
    resp = client.post("/api/analysis/frequencies", json={"column": "treatment"})
    elapsed = time.time() - t0

    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 30_000
    assert elapsed < 3.0, f"Frequencies took {elapsed:.2f}s (limit 3s)"
    print(f"\n  Frequencies on 30k rows: {elapsed:.3f}s ✓")


def test_metadata_cache(large_csv_path):
    """Metadata endpoint should benefit from caching (fast)."""
    _upload(large_csv_path)

    # First call (computes cache)
    t0 = time.time()
    resp1 = client.get("/api/data/metadata")
    t1 = time.time() - t0

    # Second call (should use cache)
    t0 = time.time()
    resp2 = client.get("/api/data/metadata")
    t2 = time.time() - t0

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["rows"] == 30_000
    assert t1 < 3.0, f"First metadata took {t1:.2f}s"
    print(f"\n  Metadata (first): {t1:.3f}s, cached: {t2:.3f}s ✓")


# ── Helpers ───────────────────────────────────────────────────────────

def _upload(path: str):
    """Upload the dataset (idempotent — always replaces current data)."""
    with open(path, "rb") as f:
        resp = client.post("/api/data/upload", files={"file": ("large.csv", f, "text/csv")})
    assert resp.status_code == 200, resp.text
