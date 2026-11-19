"""The Cloud Run job wrapper: importable, and inert unless RAGAS is switched on."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PIPELINE = ROOT / "mlops" / "bigquery" / "run_pipeline.py"


def load_pipeline():
    spec = importlib.util.spec_from_file_location("run_pipeline_under_test", PIPELINE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_module_imports_without_running_the_gate():
    """Importing must not evaluate anything; the job calls main() explicitly."""
    module = load_pipeline()
    assert callable(module.main)


def test_ragas_is_off_unless_enabled(monkeypatch):
    module = load_pipeline()
    monkeypatch.delenv("RAGAS_ENABLED", raising=False)
    assert module.score_with_ragas() is None
    monkeypatch.setenv("RAGAS_ENABLED", "0")
    assert module.score_with_ragas() is None


def test_ragas_enabled_without_a_key_fails_loudly(monkeypatch):
    module = load_pipeline()
    monkeypatch.setenv("RAGAS_ENABLED", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="no provider credential"):
        module.score_with_ragas()
