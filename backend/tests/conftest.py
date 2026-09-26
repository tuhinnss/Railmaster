import pytest


@pytest.fixture(autouse=True)
def isolated_operations_dir(tmp_path, monkeypatch):
    """Field reports and control decisions are persisted (app/operations.py).
    Every test gets its own empty store, so no test reads or writes the real
    data/operations/ directory, and none sees another's reports."""
    monkeypatch.setenv("RAILMASTER_OPS_DIR", str(tmp_path / "operations"))
