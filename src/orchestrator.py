"""Orchestrate one pipeline run: dbt (custom loader + run + test) -> publish -> run log."""
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone

from .registry import get_project_root
from .pipeline_config import load_pipeline_config
from .run_log import append_run
from .dbt_run import run_dbt_pipeline
from .pipeline_run_order import topological_sort_pipelines


def run_all_pipelines(
    project_root: Path | None = None,
    stop_on_failure: bool = True,
) -> tuple[list[dict], str | None]:
    """
    Run every pipeline in dependency order (topological sort).
    Returns (list of run results in order, first_error_or_none).
    """
    root = project_root or get_project_root()
    order = topological_sort_pipelines(root)
    results: list[dict] = []
    first_err: str | None = None
    for name in order:
        r = run_pipeline(name, root)
        results.append({"pipeline": name, **r})
        if r.get("status") != "success" and stop_on_failure:
            first_err = r.get("error", "failed")
            break
    return results, first_err


def run_pipeline(
    pipeline_name: str,
    project_root: Path | None = None,
) -> dict:
    """
    Run one pipeline: dbt run + test -> export CSV -> log.
    Pipeline YAML must use transform.type: dbt and transform.model.
    """
    root = project_root or get_project_root()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    def _timing():
        return (
            started_at,
            datetime.now(timezone.utc).isoformat(),
            round(time.perf_counter() - t0, 3),
        )

    def log_failed(error: str, **extra):
        sa, fa, dur = _timing()
        append_run(
            run_id=run_id,
            pipeline=pipeline_name,
            status="failed",
            error=error,
            started_at=sa,
            finished_at=fa,
            duration_seconds=dur,
            project_root=root,
            **extra,
        )

    try:
        config = load_pipeline_config(pipeline_name, root)
    except (FileNotFoundError, ValueError) as e:
        log_failed(str(e))
        _, _, dur = _timing()
        return {"run_id": run_id, "status": "failed", "error": str(e), "duration_seconds": dur}

    output_name = config.get("output", pipeline_name)
    transform = config.get("transform", {})
    transform_type = transform.get("type", "dbt")

    if transform_type != "dbt":
        err = f"Only transform.type: dbt is supported (got {transform_type!r})"
        log_failed(err)
        _, _, dur = _timing()
        return {"run_id": run_id, "status": "failed", "error": err, "duration_seconds": dur}

    model_name = transform.get("model", pipeline_name)
    success, df, validation_summary = run_dbt_pipeline(model_name, root)
    if not success or df is None:
        sa, fa, dur = _timing()
        append_run(
            run_id=run_id,
            pipeline=pipeline_name,
            status="failed",
            validation_summary=validation_summary,
            error=validation_summary.get("export_error", "dbt run or test failed"),
            started_at=sa,
            finished_at=fa,
            duration_seconds=dur,
            project_root=root,
        )
        return {
            "run_id": run_id,
            "status": "failed",
            "validation_summary": validation_summary,
            "error": validation_summary.get("export_error", "dbt run or test failed"),
            "duration_seconds": dur,
        }
    if not validation_summary.get("all_critical_passed", True):
        sa, fa, dur = _timing()
        append_run(
            run_id=run_id,
            pipeline=pipeline_name,
            status="failed",
            validation_summary=validation_summary,
            error="dbt tests failed",
            started_at=sa,
            finished_at=fa,
            duration_seconds=dur,
            project_root=root,
        )
        return {
            "run_id": run_id,
            "status": "failed",
            "validation_summary": validation_summary,
            "error": "dbt tests failed",
            "duration_seconds": dur,
        }

    curated_dir = root / "data" / "curated" / output_name
    curated_dir.mkdir(parents=True, exist_ok=True)
    output_path = curated_dir / f"{run_id}.csv"
    df.to_csv(output_path, index=False)
    latest_path = curated_dir / "latest.csv"
    df.to_csv(latest_path, index=False)
    rel_path = str(output_path.relative_to(root))

    sa, fa, dur = _timing()
    append_run(
        run_id=run_id,
        pipeline=pipeline_name,
        status="success",
        validation_summary=validation_summary,
        output_path=rel_path,
        started_at=sa,
        finished_at=fa,
        duration_seconds=dur,
        project_root=root,
    )

    return {
        "run_id": run_id,
        "status": "success",
        "validation_summary": validation_summary,
        "output_path": rel_path,
        "duration_seconds": dur,
    }
