"""Generate docs/RUN_HISTORY.md from runs/runs.json (recent runs + duration)."""
from pathlib import Path
from typing import Any

from .lld_flow_doc import format_lld_flow_markdown
from .registry import get_project_root
from .run_log import get_runs_dir


def load_runs(project_root: Path | None = None) -> list[dict[str, Any]]:
    path = get_runs_dir(project_root) / "runs.json"
    if not path.exists():
        return []
    import json

    with open(path) as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("runs", [])


def _run_history_table_markdown(limit: int, project_root: Path | None) -> list[str]:
    runs = load_runs(project_root)
    recent = list(reversed(runs[-limit:])) if runs else []
    lines = [
        "| Run ID | Pipeline | Status | Runtime (s) | Started (UTC) | Finished (UTC) |",
        "|--------|----------|--------|-------------|---------------|----------------|",
    ]
    for r in recent:
        rid = str(r.get("run_id", "")).replace("|", "\\|")
        pipe = str(r.get("pipeline", "")).replace("|", "\\|")
        st = str(r.get("status", ""))
        dur = r.get("duration_seconds")
        dur_s = f"{dur}" if dur is not None else "—"
        sa = str(r.get("started_at") or "—").replace("|", "\\|")
        fa = str(r.get("finished_at") or "—").replace("|", "\\|")
        lines.append(f"| `{rid}` | {pipe} | {st} | {dur_s} | {sa} | {fa} |")
    if not recent:
        lines.append("")
        lines.append("*No runs recorded yet. Run a pipeline with `python run.py <name>`.*")
    return lines


def format_run_history_markdown(limit: int = 10, project_root: Path | None = None) -> str:
    """Markdown: table of last `limit` runs, newest first, with runtime when present."""
    intro = [
        "# Pipeline run history (recent)",
        "",
        f"Last **{limit}** runs from `runs/runs.json`. **Runtime** is end-to-end for that pipeline (load raw → dbt run/test → export CSV), not per SQL statement.",
        "",
        "Re-generate: `python run.py --runs-write`",
        "",
        "---",
        "",
        format_lld_flow_markdown(),
        "---",
        "",
    ]
    return "\n".join(intro + _run_history_table_markdown(limit, project_root) + [""])


def format_dbt_doc_pipeline_runs(limit: int = 10, project_root: Path | None = None) -> str:
    """Content for dbt {% docs pipeline_runs %} … {% enddocs %} (shown in dbt Docs)."""
    lines = [
        "## Orchestrator run history",
        "",
        f"Last **{limit}** runs from the repo `runs/runs.json`. **Runtime (s)** = full pipeline (load raw → dbt run/test → export CSV), not per model.",
        "",
        "Update this page: `python run.py --runs-write` then `python run.py --docs` (or `--docs-serve`).",
        "",
        "---",
        "",
        *format_lld_flow_markdown().splitlines(),
        "",
        "---",
        "",
        *_run_history_table_markdown(limit, project_root),
        "",
    ]
    return "\n".join(lines)


def write_dbt_doc_pipeline_runs(limit: int = 10, project_root: Path | None = None) -> Path:
    """Write dbt_project/docs/pipeline_runs.md for doc('pipeline_runs') in dbt Docs."""
    root = project_root or get_project_root()
    body = format_dbt_doc_pipeline_runs(limit=limit, project_root=root)
    doc_dir = root / "dbt_project" / "docs"
    doc_dir.mkdir(parents=True, exist_ok=True)
    path = doc_dir / "pipeline_runs.md"
    wrapped = "{% docs pipeline_runs %}\n" + body + "\n{% enddocs %}\n"
    path.write_text(wrapped)
    return path


def write_run_history_doc(limit: int = 10, project_root: Path | None = None) -> Path:
    """Write docs/RUN_HISTORY.md and sync dbt doc block for docs serve."""
    root = project_root or get_project_root()
    out = root / "docs" / "RUN_HISTORY.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_run_history_markdown(limit=limit, project_root=root))
    write_dbt_doc_pipeline_runs(limit=limit, project_root=root)
    return out
