"""Load raw datasets from registry into DuckDB (schema raw) for dbt to use."""
from pathlib import Path
from typing import Any

import duckdb

from .registry import get_project_root, load_registry, get_dataset_path


def get_warehouse_path(project_root: Path | None = None) -> Path:
    """Path to the single DuckDB file used by dbt and loader."""
    root = project_root or get_project_root()
    warehouse = root / "data" / "warehouse.duckdb"
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    return warehouse


def load_raw_into_duckdb(project_root: Path | None = None) -> Path:
    """
    Create schema raw and load all raw-type datasets from registry into DuckDB.
    Returns path to warehouse.duckdb.
    """
    root = project_root or get_project_root()
    warehouse = get_warehouse_path(root)
    reg = load_registry(root)
    datasets = reg.get("datasets", {})

    con = duckdb.connect(str(warehouse))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for name, meta in datasets.items():
        if meta.get("type") != "raw":
            continue
        path = get_dataset_path(name, root)
        if not path.exists():
            continue
        path_str = str(path.resolve()).replace("'", "''")
        table_name = f"raw.{name}"
        if path.suffix.lower() in (".parquet", ".pq"):
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{path_str}')")
        else:
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{path_str}')")
    con.close()
    return warehouse
