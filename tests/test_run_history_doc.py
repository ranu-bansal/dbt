"""Tests for run history doc generation."""
import json
from pathlib import Path

from src.run_history_doc import format_run_history_markdown


def test_empty_runs(tmp_path, monkeypatch):
    monkeypatch.setattr("src.run_history_doc.get_runs_dir", lambda p=None: tmp_path)
    md = format_run_history_markdown(limit=10, project_root=tmp_path)
    assert "No runs recorded" in md
    assert "LLD: Orchestrator flow" in md
    assert "load_raw_into_duckdb" in md


def test_table_with_duration(tmp_path, monkeypatch):
    monkeypatch.setattr("src.run_history_doc.get_runs_dir", lambda p=None: tmp_path)
    runs = [
        {
            "run_id": "r1",
            "pipeline": "stg_orders",
            "status": "success",
            "duration_seconds": 1.234,
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
        }
    ]
    (tmp_path / "runs.json").write_text(json.dumps(runs))
    md = format_run_history_markdown(limit=10, project_root=tmp_path)
    assert "stg_orders" in md
    assert "1.234" in md
    assert "Runtime (s)" in md
