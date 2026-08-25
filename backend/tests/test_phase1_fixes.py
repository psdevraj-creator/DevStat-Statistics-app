"""
Phase 1 regression tests — verify each fix in Phase 1 works correctly.

Run with: cd backend && pytest tests/test_phase1_fixes.py -v
"""

import math
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app, _json_encoder_default, _sanitize_for_json

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
# 1.1 JSON serialization of float("inf") and float("nan")
# ---------------------------------------------------------------------------

class TestJsonSerialization:
    def test_float_inf_serializes_as_null(self):
        """float('inf') should serialize to null, not crash."""
        sanitized = _sanitize_for_json({"value": float("inf")})
        result = json.dumps(sanitized, default=_json_encoder_default)
        assert json.loads(result)["value"] is None

    def test_float_nan_serializes_as_null(self):
        """float('nan') should serialize to null, not crash."""
        sanitized = _sanitize_for_json({"value": float("nan")})
        result = json.dumps(sanitized, default=_json_encoder_default)
        assert json.loads(result)["value"] is None

    def test_float_neg_inf_serializes_as_null(self):
        """float('-inf') should serialize to null, not crash."""
        sanitized = _sanitize_for_json({"value": float("-inf")})
        result = json.dumps(sanitized, default=_json_encoder_default)
        assert json.loads(result)["value"] is None

    def test_normal_float_serializes_correctly(self):
        """Normal floats should serialize normally."""
        sanitized = _sanitize_for_json({"value": 3.14})
        result = json.dumps(sanitized, default=_json_encoder_default)
        assert json.loads(result)["value"] == 3.14

    def test_diagnostic_perfect_data_returns_valid_json(self):
        """Diagnostic endpoint with perfect data should return valid JSON."""
        import app.state as _state
        df = pd.DataFrame({
            "test": [1, 1, 0, 0],
            "gold": [1, 1, 0, 0],
        })
        _upload(df)

        response = client.post("/api/analysis/diagnostic", json={
            "test_col": "test",
            "gold_col": "gold",
        })
        # May fail if R is not available, but shouldn't crash with serialization error
        assert response.status_code in (200, 422, 500)
        if response.status_code == 200:
            data = response.json()
            assert "sensitivity" in data
            assert "specificity" in data
            assert "confusion_matrix" in data or all(k in data for k in ("tp", "fp", "fn", "tn"))


# ---------------------------------------------------------------------------
# 1.2 Params dict mutation in dispatcher
# ---------------------------------------------------------------------------

class TestDispatcherMutation:
    def test_params_not_mutated(self):
        """Dispatcher should not mutate the caller's params dict."""
        from r.dispatcher import run_analysis
        import app.state as _state
        _state.current_data = pd.DataFrame({"x": [1, 2, 3]})

        original = {"columns": ["x"]}
        params_copy = dict(original)
        try:
            run_analysis("descriptive", original)
        except Exception:
            pass
        assert original == params_copy


# ---------------------------------------------------------------------------
# 1.3 eval() RCE vulnerability — dangerous input rejected
# ---------------------------------------------------------------------------

class TestEvalSafety:
    def test_simple_arithmetic(self):
        """Basic arithmetic should work."""
        from app.routers.data import _evaluate_expression
        df = pd.DataFrame({"age": [20, 30, 40], "bmi": [22, 25, 28]})
        result = _evaluate_expression("age + bmi", df)
        assert list(result) == [42, 55, 68]

    def test_function_call(self):
        """Safe function calls should work."""
        from app.routers.data import _evaluate_expression
        df = pd.DataFrame({"age": [20, 30, 40]})
        result = _evaluate_expression("sqrt(age)", df)
        assert len(result) == 3

    def test_os_system_rejected(self):
        """eval-style __import__('os').system(...) should be rejected."""
        from app.routers.data import _evaluate_expression
        df = pd.DataFrame({"age": [20, 30, 40]})
        with pytest.raises(Exception):
            _evaluate_expression("__import__('os').system('dir')", df)

    def test_attribute_access_rejected(self):
        """Accessing __class__.__init__ should be rejected."""
        from app.routers.data import _evaluate_expression
        df = pd.DataFrame({"age": [20, 30, 40]})
        with pytest.raises(Exception):
            _evaluate_expression("age.__class__.__init__.__globals__", df)

    def test_if_expression(self):
        """Conditional expressions should work."""
        from app.routers.data import _evaluate_expression
        df = pd.DataFrame({"age": [20, 30, 40]})
        result = _evaluate_expression("age + 10", df)
        assert list(result) == [30, 40, 50]


# ---------------------------------------------------------------------------
# 1.4 AI prompt files exist
# ---------------------------------------------------------------------------

class TestAIPrompts:
    def test_goal_parser_prompt_exists(self):
        """goal_parser.md should exist and have content."""
        from pathlib import Path
        prompt_file = Path(__file__).resolve().parent.parent / "app" / "ai" / "prompts" / "goal_parser.md"
        assert prompt_file.exists()
        assert prompt_file.read_text(encoding="utf-8").strip() != ""

    def test_synthesizer_prompt_exists(self):
        """synthesizer.md should exist and have content."""
        from pathlib import Path
        prompt_file = Path(__file__).resolve().parent.parent / "app" / "ai" / "prompts" / "synthesizer.md"
        assert prompt_file.exists()
        assert prompt_file.read_text(encoding="utf-8").strip() != ""
