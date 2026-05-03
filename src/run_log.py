"""Append run log (run_id, pipeline, status, validation summary) to runs/runs.json."""
import json
from pathlib import Path
from typing import Any

from .registry import get_project_root


def get_runs_dir(project_root: Path | None = None) -> Path:
    root = project_root or get_project_root()
    d = root / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_run(
    run_id: str,
    pipeline: str,
    status: str,
    validation_summary: dict[str, Any] | None = None,
    output_path: str | None = None,
    error: str | None = None,
    project_root: Path | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_seconds: float | None = None,
) -> Path:
    """Append one run record to runs/runs.json (or create file)."""
    runs_dir = get_runs_dir(project_root)
    path = runs_dir / "runs.json"
    record: dict[str, Any] = {
        "run_id": run_id,
        "pipeline": pipeline,
        "status": status,
        "validation_summary": validation_summary,
        "output_path": output_path,
        "error": error,
    }
    if started_at is not None:
        record["started_at"] = started_at
    if finished_at is not None:
        record["finished_at"] = finished_at
    if duration_seconds is not None:
        record["duration_seconds"] = duration_seconds
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        runs = data if isinstance(data, list) else data.get("runs", [])
    else:
        runs = []
    runs.append(record)
    with open(path, "w") as f:
        json.dump(runs, f, indent=2)
    return path
