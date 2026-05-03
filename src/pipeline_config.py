"""Load and validate pipeline YAML from config/pipelines/."""
from pathlib import Path
from typing import Any

import yaml

from .registry import get_project_root


def load_pipeline_config(pipeline_name: str, project_root: Path | None = None) -> dict[str, Any]:
    """Load pipeline YAML from config/pipelines/<name>.yaml."""
    root = project_root or get_project_root()
    path = root / "config" / "pipelines" / f"{pipeline_name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    if not config or not isinstance(config, dict):
        raise ValueError(
            f"Pipeline config is empty or invalid YAML: {path}. "
            "Save the file with at least name, transform, and output."
        )
    validate_pipeline_config(config, path)
    return config


def validate_pipeline_config(config: dict[str, Any], path: Path) -> None:
    """Ensure required keys for dbt pipelines."""
    label = str(path)
    if not config.get("output"):
        raise ValueError(f"Pipeline {label} must set 'output' (curated dataset name).")
    transform = config.get("transform")
    if not transform or not isinstance(transform, dict):
        raise ValueError(f"Pipeline {label} must include a 'transform' mapping.")
    ttype = transform.get("type", "dbt")
    if ttype != "dbt":
        raise ValueError(f"Pipeline {label}: only transform.type: dbt is supported (got {ttype!r}).")
    if not transform.get("model"):
        raise ValueError(
            f"Pipeline {label}: transform.model is required (dbt model name, e.g. stg_orders)."
        )
