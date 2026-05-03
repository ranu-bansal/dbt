"""Tests for pipeline topological order."""
from src.pipeline_run_order import topological_sort_pipelines


def test_stg_orders_before_orders_enriched():
    order = topological_sort_pipelines()
    assert order.index("stg_orders") < order.index("orders_enriched")
