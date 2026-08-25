import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def test_signed_in_licensed(monkeypatch):
    """Run regression tests as a signed-in, licensed user.

    Under the product's free-tier model, unauthored compute is blocked (no
    anonymous use) and a machine+IP trial counter caps free usage. These tests
    assert engine/endpoint behaviour, not the gate, so we satisfy the gate by:
      - making the session middleware resolve a uid (peek_uid), and
      - treating that uid as licensed (unlimited), so the trial counter is not
        consumed or exhausted across the suite.
    The free-tier gate itself is covered by dedicated tests.
    """
    import app.state as _state
    import app.services.firebase_store as fs
    monkeypatch.setattr(_state, "get_uid", lambda: "testuid")
    monkeypatch.setattr(_state, "get_device", lambda: "testdevice")
    monkeypatch.setattr(fs, "licence_live", lambda uid: True)
    yield
