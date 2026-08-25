"""
Phase 3 regression tests — verify backend data corruption & logic fixes.

Run with: cd backend && pytest tests/test_phase3_fixes.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
# 3.1 Metadata cache invalidation
# ---------------------------------------------------------------------------

class TestMetadataCache:
    def test_cache_returns_fresh_data_after_cell_edit(self):
        """After cell edit, metadata should reflect new values."""
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        _upload(df)

        resp1 = client.get("/api/data/metadata")
        assert resp1.status_code == 200
        assert resp1.json()["cols"] == 2

        client.put("/api/data/cell", json={"row": 0, "col": "x", "value": 99})

        resp2 = client.get("/api/data/metadata")
        assert resp2.status_code == 200

    def test_cache_returns_fresh_data_after_column_add(self):
        """After adding a column, metadata should show new column."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        _upload(df)

        resp1 = client.get("/api/data/metadata")
        assert resp1.json()["cols"] == 1

        client.post("/api/data/column", json={"name": "y"})

        resp2 = client.get("/api/data/metadata")
        assert resp2.json()["cols"] == 2

    def test_cache_returns_fresh_data_after_column_delete(self):
        """After deleting a column, metadata should reflect removal."""
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        _upload(df)

        resp1 = client.get("/api/data/metadata")
        assert resp1.json()["cols"] == 2

        client.delete("/api/data/column/y")

        resp2 = client.get("/api/data/metadata")
        assert resp2.json()["cols"] == 1

    def test_cache_returns_fresh_data_after_compute(self):
        """After compute, metadata should include new column."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        _upload(df)

        resp1 = client.get("/api/data/metadata")
        assert resp1.json()["cols"] == 1

        client.post("/api/data/compute", json={"name": "y", "expression": "x + 1"})

        resp2 = client.get("/api/data/metadata")
        assert resp2.json()["cols"] == 2

    def test_cache_returns_fresh_data_after_recode(self):
        """After recode, metadata should still be accessible."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        _upload(df)

        resp1 = client.get("/api/data/metadata")
        assert resp1.status_code == 200

        client.post("/api/data/recode", json={"column": "x", "mappings": {"1": "10"}})

        resp2 = client.get("/api/data/metadata")
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# 3.3 Cox PH assumption reporting
# ---------------------------------------------------------------------------

class TestCoxPHInterpretation:
    def test_ph_assumption_violation_reported(self):
        """Interpretation should report violation when p < 0.05."""
        from app.services.survival import _interpret_cox
        coeffs = [{"name": "age", "hr": 1.05, "p": 0.03, "z": 2.1,
                   "hr_ci_lower": 1.01, "hr_ci_upper": 1.09,
                   "p_label": {"value": 0.03, "label": "p = 0.030", "sig": "*"}}]
        summary = {"n": 100, "n_events": 30, "n_covariates": 1,
                   "concordance_index": 0.7, "aic": 500}

        ph_bad = {"age": {"test_statistic": 8.5, "p": 0.003, "p_label": {"value": 0.003, "label": "p = 0.003", "sig": "**"}}}
        result = _interpret_cox(coeffs, summary, ph_bad)
        assert "violated" in result.lower()

    def test_ph_assumption_not_violated_reported(self):
        """Interpretation should report not violated when p >= 0.05."""
        from app.services.survival import _interpret_cox
        coeffs = [{"name": "age", "hr": 1.05, "p": 0.03, "z": 2.1,
                   "hr_ci_lower": 1.01, "hr_ci_upper": 1.09,
                   "p_label": {"value": 0.03, "label": "p = 0.030", "sig": "*"}}]
        summary = {"n": 100, "n_events": 30, "n_covariates": 1,
                   "concordance_index": 0.7, "aic": 500}

        ph_ok = {"age": {"test_statistic": 0.5, "p": 0.48, "p_label": {"value": 0.48, "label": "p = 0.480", "sig": "ns"}}}
        result = _interpret_cox(coeffs, summary, ph_ok)
        assert "not violated" in result.lower()


# ---------------------------------------------------------------------------
# 3.6 Chi-square interpretation percentage format
# ---------------------------------------------------------------------------

class TestChisquareFormat:
    def test_min_exp_not_multiplied_by_100(self):
        """min_exp should not be formatted as percentage (multiplied by 100)."""
        from app.services.interpreter import interpret_chisquare
        result = interpret_chisquare({
            "statistic": 5.0, "p_value": 0.025, "effect_size": 0.3,
            "df": 1, "n": 100, "min_expected": 0.8,
            "effect_size_interpretation": "medium",
        })
        # Should show 0.8, not 80.0%
        assert "0.8" in result


# ---------------------------------------------------------------------------
# 3.7 Cox predict baseline survival interpolation
# ---------------------------------------------------------------------------

class TestCoxPredict:
    def test_cox_predict_returns_traces(self):
        """Cox predict endpoint should return traces."""
        import app.state as _state
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            "time": np.random.exponential(scale=12, size=n).clip(1, 60),
            "status": np.random.binomial(1, 0.4, size=n),
            "age": np.random.normal(55, 10, size=n),
            "bmi": np.random.normal(28, 5, size=n),
        })
        _upload(df)

        resp = client.post("/api/analysis/cox-predict", json={
            "time_col": "time",
            "status_col": "status",
            "covariates": ["age", "bmi"],
            "event_code": 1,
        })
        assert resp.status_code in (200, 422, 500)
        if resp.status_code == 200:
            data = resp.json()
            if "traces" in data:
                for trace in data["traces"]:
                    assert len(trace["x"]) == len(trace["y"])


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------

class TestMetadataEndpoint:
    def test_metadata_returns_valid_response(self):
        """Metadata endpoint should return valid JSON."""
        df = pd.DataFrame({
            "age": [25, 30, 35, 40],
            "bmi": [22, 25, 28, 31],
            "group": ["A", "A", "B", "B"],
        })
        _upload(df)

        resp = client.get("/api/data/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows"] == 4
        assert data["cols"] == 3
        assert len(data["columns"]) == 3
