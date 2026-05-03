"""Load dataset registry and resolve paths."""
from pathlib import Path
from typing import Any

import yaml


def get_project_root() -> Path:
    """Project root = directory containing run.py (quince_demo)."""
    return Path(__file__).resolve().parent.parent


def load_registry(project_root: Path | None = None) -> dict[str, Any]:
    """Load registry.yaml; return dict with 'datasets' key."""
    root = project_root or get_project_root()
    path = root / "config" / "registry.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if data else {"datasets": {}}


def get_dataset_path(dataset_name: str, project_root: Path | None = None) -> Path:
    """Resolve absolute path for a registered dataset."""
    root = project_root or get_project_root()
    reg = load_registry(root)
    datasets = reg.get("datasets", {})
    if dataset_name not in datasets:
        raise KeyError(f"Dataset not in registry: {dataset_name}")
    rel = datasets[dataset_name].get("path")
    if not rel:
        raise ValueError(f"Dataset {dataset_name} has no path")
    return (root / rel).resolve()


def list_datasets(project_root: Path | None = None) -> list[str]:
    """Return list of registered dataset names."""
    reg = load_registry(project_root)
    return list(reg.get("datasets", {}).keys())
