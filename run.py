#!/usr/bin/env python3
"""CLI: run a pipeline. Usage: python run.py <pipeline_name>"""
import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.orchestrator import run_all_pipelines, run_pipeline
from src.pipeline_run_order import topological_sort_pipelines
from src.pipeline_config import load_pipeline_config
from src.registry import get_project_root
from src.run_log import get_runs_dir
from src.lineage import (
    format_lineage,
    format_full_graph,
    format_lineage_mermaid,
    write_lineage_docs,
    write_lineage_html,
)
from src.run_history_doc import write_run_history_doc


def _dbt_bin() -> str:
    b = Path(sys.executable).parent / "dbt"
    return str(b) if b.exists() else "dbt"


def cmd_dbt_docs(serve: bool = False) -> int:
    """Run dbt docs generate (and optionally serve) with correct DuckDB path."""
    root = get_project_root()
    dbt_dir = root / "dbt_project"
    if not dbt_dir.is_dir():
        print("dbt_project/ not found", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["QUINCE_DUCKDB_PATH"] = str(root / "data" / "warehouse.duckdb")
    env["DBT_PROFILES_DIR"] = str(dbt_dir)
    exe = _dbt_bin()
    # Embed latest run history into dbt Docs (doc block + analyses/pipeline_runs)
    write_run_history_doc(limit=10, project_root=root)
    r = subprocess.run([exe, "docs", "generate"], cwd=str(dbt_dir), env=env)
    if r.returncode != 0:
        return r.returncode
    if serve:
        print("Starting docs server (Ctrl+C to stop)…", file=sys.stderr)
        r = subprocess.run([exe, "docs", "serve"], cwd=str(dbt_dir), env=env)
    else:
        print(f"Open with: cd dbt_project && {exe} docs serve", file=sys.stderr)
        print("(same QUINCE_DUCKDB_PATH and DBT_PROFILES_DIR as above)", file=sys.stderr)
    return r.returncode if serve else 0


def list_runs(project_root: Path | None = None, limit: int = 10) -> None:
    """Print recent runs from runs/runs.json."""
    root = project_root or get_project_root()
    path = get_runs_dir(root) / "runs.json"
    if not path.exists():
        print("No runs yet.")
        return
    with open(path) as f:
        runs = json.load(f)
    for r in (runs if isinstance(runs, list) else runs.get("runs", []))[-limit:][::-1]:
        print(f"  {r.get('run_id')}  {r.get('pipeline')}  {r.get('status')}")


def show_run(run_id: str, project_root: Path | None = None) -> bool:
    """Print full run log for run_id. Returns True if found."""
    root = project_root or get_project_root()
    path = get_runs_dir(root) / "runs.json"
    if not path.exists():
        return False
    with open(path) as f:
        runs = json.load(f)
    for r in (runs if isinstance(runs, list) else []):
        if r.get("run_id") == run_id:
            print(json.dumps(r, indent=2))
            return True
    return False


def list_pipelines() -> None:
    root = get_project_root()
    pipelines_dir = root / "config" / "pipelines"
    if not pipelines_dir.exists():
        print("No pipelines found (config/pipelines/ missing)")
        return
    for f in sorted(pipelines_dir.glob("*.yaml")):
        name = f.stem
        try:
            config = load_pipeline_config(name, root)
            desc = config.get("description", "")
            print(f"  {name}: {desc}")
        except Exception:
            print(f"  {name}")
    print()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python run.py <pipeline_name>")
        print("       python run.py --list            # list pipelines")
        print("       python run.py --runs [N]        # list last N runs (default 10)")
        print("       python run.py --run <run_id>     # show run log")
        print("       python run.py --lineage [name]   # text lineage (or full list)")
        print("       python run.py --lineage-graph    # Mermaid graph to stdout")
        print("       python run.py --lineage-write    # write docs/LINEAGE.md + lineage_graph.html")
        print("       python run.py --runs-write [N]   # write docs/RUN_HISTORY.md (last N runs, default 10)")
        print("       python run.py --docs-write       # lineage + run history markdown/html")
        print("       python run.py --docs             # dbt docs generate (sets DuckDB env)")
        print("       python run.py --docs-serve       # generate + dbt docs serve")
        print("       python run.py --all              # run all pipelines (dependency order)")
        print()
        print("Pipelines:")
        list_pipelines()
        return 0

    if sys.argv[1] in ("--list", "-l"):
        list_pipelines()
        return 0
    if sys.argv[1] == "--runs":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        list_runs(limit=limit)
        return 0
    if sys.argv[1] == "--run" and len(sys.argv) >= 3:
        if show_run(sys.argv[2]):
            return 0
        print(f"Run not found: {sys.argv[2]}", file=sys.stderr)
        return 1
    if sys.argv[1] == "--lineage":
        if len(sys.argv) >= 3:
            print(format_lineage(sys.argv[2]))
        else:
            print(format_full_graph())
        return 0
    if sys.argv[1] == "--lineage-graph":
        print(format_lineage_mermaid())
        return 0
    if sys.argv[1] == "--lineage-write":
        md = write_lineage_docs()
        html = write_lineage_html()
        print(f"Wrote {md}")
        print(f"Wrote {html}")
        return 0
    if sys.argv[1] == "--runs-write":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        p = write_run_history_doc(limit=n)
        print(f"Wrote {p}")
        return 0
    if sys.argv[1] == "--docs-write":
        md = write_lineage_docs()
        html = write_lineage_html()
        rh = write_run_history_doc(limit=10)
        print(f"Wrote {md}")
        print(f"Wrote {html}")
        print(f"Wrote {rh}")
        return 0
    if sys.argv[1] == "--docs":
        return cmd_dbt_docs(serve=False)
    if sys.argv[1] == "--docs-serve":
        return cmd_dbt_docs(serve=True)
    if sys.argv[1] in ("--all", "-a"):
        try:
            order = topological_sort_pipelines()
            print("Pipeline run order (dependencies first):")
            for i, n in enumerate(order, 1):
                print(f"  {i}. {n}")
            print()
            results, err = run_all_pipelines()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        ok = all(r.get("status") == "success" for r in results if "pipeline" in r)
        for r in results:
            p = r.get("pipeline", "?")
            st = r.get("status", "?")
            ds = r.get("duration_seconds", "")
            out = r.get("output_path", "")
            line = f"  {p}: {st}"
            if ds != "":
                line += f" ({ds}s)"
            if out:
                line += f" -> {out}"
            print(line)
        if err:
            print(f"Stopped after first failure: {err}", file=sys.stderr)
            return 1
        return 0 if ok and len(results) == len(order) else 1

    pipeline_name = sys.argv[1]
    try:
        result = run_pipeline(pipeline_name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"run_id: {result['run_id']}")
    print(f"status: {result['status']}")
    ds = result.get("duration_seconds")
    if ds is not None:
        print(f"duration_seconds: {ds}")
    if result.get("output_path"):
        print(f"output: {result['output_path']}")
    if result.get("validation_summary") and not result["validation_summary"].get("all_critical_passed"):
        print("validation:", json.dumps(result["validation_summary"], indent=2))
    if result.get("error"):
        print(f"error: {result['error']}", file=sys.stderr)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
