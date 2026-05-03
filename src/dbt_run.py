"""Run dbt (run + test), parse results, export model from DuckDB to DataFrame."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .registry import get_project_root
from .dbt_loader import get_warehouse_path, load_raw_into_duckdb

# dbt colorizes stderr; strip so runs.json stays readable without ANSI escape sequences
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
# Typical dbt log prefix: "21:22:55  "
_DBT_LINE_TIME = re.compile(r"^\d{2}:\d{2}:\d{2}\s+")


def _humanize_dbt_output(text: str) -> str:
    """
    Plain-text dbt errors for runs.json: strip ANSI, drop timestamps, trim noise.

    Removes: leading 'ERROR creating' boilerplate when 'Failure in model' exists,
    'Done. PASS=...' tail, and dbt deprecation summaries.
    """
    if not text:
        return ""
    s = _ANSI_ESCAPE.sub("", text)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")

    # Drop tail noise (deprecations, Done summary)
    trimmed: list[str] = []
    for line in lines:
        if "[WARNING][DeprecationsSummary]" in line:
            break
        if "Summary of encountered deprecations:" in line:
            break
        # dbt prints "HH:MM:SS  Done. PASS=..." — timestamp prefix on same line
        if "Done." in line and "PASS=" in line and "TOTAL=" in line:
            break
        trimmed.append(line)
    lines = trimmed

    # Prefer the real failure block (not the earlier "ERROR creating" line)
    start_idx: int | None = None
    for i, line in enumerate(lines):
        if "Failure in model" in line or "Failure in test" in line:
            start_idx = i
            break
    if start_idx is None:
        for i, line in enumerate(lines):
            if "Compilation Error" in line:
                start_idx = i
                break
    if start_idx is None:
        for i, line in enumerate(lines):
            if (
                "ERROR creating" in line
                or "Runtime Error" in line
                or "Encountered an error" in line
            ):
                start_idx = i
                break
    if start_idx is not None:
        lines = lines[start_idx:]

    lines = [_DBT_LINE_TIME.sub("", line) for line in lines]

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop(-1)

    out = "\n".join(lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    out = out.strip()
    max_len = 12000
    if len(out) > max_len:
        out = "...[log truncated]\n\n" + out[-max_len:]
    return out


def _dbt_project_dir(project_root: Path | None = None) -> Path:
    root = project_root or get_project_root()
    return root / "dbt_project"


def _export_model_from_duckdb(warehouse: Path, model_name: str) -> pd.DataFrame:
    """Export model table from DuckDB. dbt-duckdb uses main_staging / main_marts (try both)."""
    con = duckdb.connect(str(warehouse))
    for prefix in ("main_staging", "main_marts", "staging", "marts", "quince_staging", "quince_marts"):
        try:
            df = con.execute(f'SELECT * FROM "{prefix}"."{model_name}"').fetchdf()
            con.close()
            return df
        except Exception:
            continue
    con.close()
    raise RuntimeError(f'Model table "{model_name}" not found under main_staging/main_marts in {warehouse}')


def run_dbt_pipeline(
    model_name: str,
    project_root: Path | None = None,
) -> tuple[bool, pd.DataFrame | None, dict[str, Any]]:
    """
    Load raw into DuckDB, run dbt run --select model+, dbt test --select model,
    export model to DataFrame. Returns (success, df, validation_summary).
    """
    root = project_root or get_project_root()
    dbt_dir = _dbt_project_dir(root)
    if not dbt_dir.exists():
        return False, None, {"error": "dbt_project not found"}

    warehouse = load_raw_into_duckdb(root)
    env = os.environ.copy()
    env["QUINCE_DUCKDB_PATH"] = str(warehouse)
    env["DBT_PROFILES_DIR"] = str(dbt_dir)

    # dbt run --select model+ (use venv's dbt if available)
    dbt_bin = Path(sys.executable).parent / "dbt"
    if not dbt_bin.exists():
        dbt_bin = "dbt"
    # --no-use-colors: plain text in captured stderr (readable in runs.json)
    run_cmd = [str(dbt_bin), "--no-use-colors", "run", "--select", f"{model_name}+"]
    res_run = subprocess.run(
        run_cmd,
        cwd=str(dbt_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    if res_run.returncode != 0:
        raw = res_run.stderr or res_run.stdout or ""
        return False, None, {
            "all_critical_passed": False,
            "results": [{"rule": "dbt_run", "passed": False, "message": _humanize_dbt_output(raw), "severity": "critical"}],
        }

    # dbt test --select model
    test_cmd = [str(dbt_bin), "--no-use-colors", "test", "--select", model_name]
    res_test = subprocess.run(
        test_cmd,
        cwd=str(dbt_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    run_results_path = dbt_dir / "target" / "run_results.json"
    validation_results = []
    if run_results_path.exists():
        with open(run_results_path) as f:
            run_results = json.load(f)
        for r in run_results.get("results", []):
            validation_results.append({
                "rule": r.get("unique_id", r.get("message", "test")),
                "passed": r.get("status") == "pass",
                "message": r.get("message", ""),
                "severity": "critical",
            })
    all_passed = res_test.returncode == 0 and all(r.get("passed", False) for r in validation_results)
    if not all_passed and not validation_results:
        raw = res_test.stderr or res_test.stdout or ""
        validation_results = [{"rule": "dbt_test", "passed": False, "message": _humanize_dbt_output(raw), "severity": "critical"}]

    # Export model from DuckDB (staging vs marts resolved by table name)
    try:
        df = _export_model_from_duckdb(warehouse, model_name)
    except Exception as e:
        return False, None, {"all_critical_passed": all_passed, "results": validation_results, "export_error": str(e)}

    return all_passed, df, {"all_critical_passed": all_passed, "results": validation_results}
