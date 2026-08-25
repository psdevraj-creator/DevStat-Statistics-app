"""
Regression tests for DevStat backend analysis endpoints.

Covers edge cases that previously caused uncontrolled 500s:
  - numeric column (numpy.int64 serialization)
  - string column with whitespace
  - empty / all-null column
  - unknown column name
  - mixed dtype column
  - zero events survival
  - single group survival
  - negative durations
  - missing dates
"""

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
import json, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.state import current_data

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_state():
    """Reset global state before each test."""
    import app.state as _state
    _state.current_data = None
    _state.current_filename = None
    _state.variable_metadata = {}
    yield
    _state.current_data = None


def _upload(df: pd.DataFrame):
    """Helper: upload a DataFrame to the test client."""
    import io
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return client.post("/api/data/upload", files={"file": ("test.csv", buf, "text/csv")})


# ---------------------------------------------------------------------------
# Frequencies
# ---------------------------------------------------------------------------

class TestFrequencies:
    def test_numeric_column(self):
        """Int64 columns must not throw PydanticSerializationError."""
        df = pd.DataFrame({"x": pd.array([1, 2, 3, 1, 2], dtype="Int64")})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "x"})
        assert resp.status_code == 200
        data = resp.json()
        assert "table" in data
        assert data["n"] == 5
        assert data["table"][0]["value"] == 1  # most frequent

    def test_string_column(self):
        """Categorical strings must produce correct counts."""
        df = pd.DataFrame({"cat": ["A", "B", "A", "C", "A"]})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "cat"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["table"]) == 3

    def test_whitespace_normalization(self):
        """Trailing spaces / duplicate-like labels must be merged."""
        df = pd.DataFrame({"regimen": [
            "50/25 CARBO PACLI",
            "50/25 CARBO PACLI ",
            "50/25 CARBO PACLI  ",
            "CISPLATIN",
        ]})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "regimen"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["table"]) == 2  # not 3
        counts = {r["value"]: r["count"] for r in data["table"]}
        assert counts.get("50/25 CARBO PACLI") == 3

    def test_unknown_column(self):
        """Unknown column must return a controlled error, not 500."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "nonexistent"})
        assert resp.status_code == 400  # or 422
        assert "detail" in resp.json()

    def test_empty_column(self):
        """All-null column must return gracefully."""
        df = pd.DataFrame({"x": [None, None, None]})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "x"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["n"] == 0
        assert data["table"] == []

    def test_mixed_type_column(self):
        """Mixed str/int column must not crash."""
        df = pd.DataFrame({"x": ["hello", 42, "world", None, 99]})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "x"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["n"] >= 1

    def test_no_data_loaded(self):
        """No dataset loaded must return 400."""
        resp = client.post("/api/analysis/frequencies", json={"column": "x"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Kaplan-Meier
# ---------------------------------------------------------------------------

class TestKaplanMeier:
    def test_basic_km(self):
        """Standard KM with events and censored."""
        df = pd.DataFrame({
            "time": [10.0, 20.0, 30.0, 40.0, 50.0],
            "status": [1, 1, 0, 1, 0],
        })
        _upload(df)
        resp = client.post("/api/analysis/kaplan-meier", json={
            "time_col": "time", "status_col": "status",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_events"] == 3
        assert data["n_censored"] == 2
        assert "km_curve" in data
        assert len(data["km_curve"]) == 1

    def test_zero_events(self):
        """All censored — must return controlled response."""
        df = pd.DataFrame({
            "time": [10.0, 20.0, 30.0],
            "status": [0, 0, 0],
        })
        _upload(df)
        resp = client.post("/api/analysis/kaplan-meier", json={
            "time_col": "time", "status_col": "status",
        })
        assert resp.status_code == 200

    def test_single_group(self):
        """KM with just one group value."""
        df = pd.DataFrame({
            "time": [10.0, 20.0, 30.0],
            "status": [1, 1, 0],
            "group": ["A", "A", "A"],
        })
        _upload(df)
        resp = client.post("/api/analysis/kaplan-meier", json={
            "time_col": "time", "status_col": "status", "factors": ["group"],
        })
        assert resp.status_code == 200

    def test_missing_column(self):
        """Bad column name must return 400, not 500."""
        df = pd.DataFrame({"x": [1, 2]})
        _upload(df)
        resp = client.post("/api/analysis/kaplan-meier", json={
            "time_col": "nonexistent", "status_col": "x",
        })
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Cox Regression
# ---------------------------------------------------------------------------

class TestCox:
    def test_basic_cox(self):
        """Standard Cox regression."""
        df = pd.DataFrame({
            "time": [10, 20, 30, 40, 50, 60],
            "status": [1, 1, 0, 1, 0, 1],
            "age": [45, 62, 58, 71, 39, 55],
        })
        _upload(df)
        resp = client.post("/api/analysis/cox-regression", json={
            "time_col": "time", "status_col": "status", "covariates": ["age"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "coefficients" in data
        assert "model_summary" in data
        assert len(data["coefficients"]) == 1

    def test_no_covariates(self):
        """Missing covariates must return 400."""
        df = pd.DataFrame({"time": [1, 2], "status": [1, 0]})
        _upload(df)
        resp = client.post("/api/analysis/cox-regression", json={
            "time_col": "time", "status_col": "status", "covariates": [],
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

class TestCharts:
    def test_histogram(self):
        df = pd.DataFrame({"age": [45, 62, 58, 71, 39, 55]})
        _upload(df)
        resp = client.post("/api/charts/histogram", json={"column": "age", "bins": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert "series" in data

    def test_histogram_non_numeric(self):
        """Non-numeric column must not crash."""
        df = pd.DataFrame({"name": ["Alice", "Bob", "Charlie"]})
        _upload(df)
        resp = client.post("/api/charts/histogram", json={"column": "name", "bins": 5})
        assert resp.status_code == 200

    def test_scatter(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [10, 20, 30, 40]})
        _upload(df)
        resp = client.post("/api/charts/scatter", json={"x_col": "x", "y_col": "y"})
        assert resp.status_code == 200

    def test_bar_chart(self):
        df = pd.DataFrame({"cat": ["A", "B", "A", "C"]})
        _upload(df)
        resp = client.post("/api/charts/bar", json={"category_col": "cat"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Survival Prep
# ---------------------------------------------------------------------------

class TestSurvivalPrep:
    def test_date_prep(self):
        df = pd.DataFrame({
            "start": ["2020-01-15", "2019-06-10", "2021-03-20"],
            "death": ["2022-03-10", None, "2023-01-15"],
            "fup": ["2022-03-10", "2023-12-01", "2023-01-15"],
        })
        _upload(df)
        resp = client.post("/api/data/survival-prep", json={
            "start_col": "start", "event_col": "death", "censor_col": "fup",
            "unit": "months", "new_time_col": "st", "new_status_col": "sev",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_events"] == 2
        assert data["n_censored"] == 1


# ---------------------------------------------------------------------------
# JSON Serialization (regression for numpy types)
# ---------------------------------------------------------------------------

class TestJsonSerialization:
    def test_int64_serialization(self):
        """numpy.int64 must serialize to plain int."""
        df = pd.DataFrame({"x": pd.array([1, 2, 3], dtype="Int64")})
        _upload(df)
        resp = client.post("/api/analysis/frequencies", json={"column": "x"})
        assert resp.status_code == 200
        raw = resp.content
        # Must NOT contain numpy references
        assert b"numpy" not in raw
        assert b"int64" not in raw.lower()

    def test_float_nan_serialization(self):
        """NaN must become JSON null."""
        df = pd.DataFrame({"x": [1.0, float('nan'), 3.0]})
        _upload(df)
        resp = client.post("/api/charts/histogram", json={"column": "x"})
        assert resp.status_code == 200
        raw = resp.content
        # NaN in JSON is illegal; our encoder converts to null
        assert b"NaN" not in raw


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
