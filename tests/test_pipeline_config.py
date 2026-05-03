"""Tests for pipeline config validation."""
from pathlib import Path

import pytest

from src.pipeline_config import load_pipeline_config, validate_pipeline_config


def test_load_stg_orders():
    cfg = load_pipeline_config("stg_orders")
    assert cfg["output"] == "stg_orders"
    assert cfg["transform"]["type"] == "dbt"
    assert cfg["transform"]["model"] == "stg_orders"


def test_empty_pipeline_file_raises(tmp_path, monkeypatch):
    (tmp_path / "config" / "pipelines").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "pipelines" / "empty.yaml").write_text("")
    monkeypatch.setattr("src.pipeline_config.get_project_root", lambda: tmp_path)
    with pytest.raises(ValueError, match="empty or invalid"):
        load_pipeline_config("empty")


def test_validate_requires_output():
    fake = Path("x.yaml")
    with pytest.raises(ValueError, match="output"):
        validate_pipeline_config({"transform": {"type": "dbt", "model": "m"}}, fake)


def test_validate_requires_model():
    fake = Path("x.yaml")
    with pytest.raises(ValueError, match="transform.model"):
        validate_pipeline_config({"output": "o", "transform": {"type": "dbt"}}, fake)
