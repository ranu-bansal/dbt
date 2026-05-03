"""Tests for registry loading."""
from pathlib import Path

import pytest

from src.registry import get_project_root, load_registry, list_datasets


def test_get_project_root():
    root = get_project_root()
    assert (root / "run.py").exists()
    assert (root / "config" / "registry.yaml").exists()


def test_load_registry():
    reg = load_registry()
    assert "datasets" in reg
    assert "orders" in reg["datasets"]


def test_list_datasets():
    names = list_datasets()
    assert "orders" in names
    assert "customers" in names
