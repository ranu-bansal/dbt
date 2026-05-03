"""Tests for lineage graph."""
from src.lineage import build_lineage_graph, format_lineage_mermaid


def test_lineage_has_pipelines():
    g = build_lineage_graph()
    assert "stg_orders" in g["pipelines"]
    assert "orders_enriched" in g["pipelines"]
    stg = g["pipelines"]["stg_orders"]
    assert stg["output"] == "stg_orders"
    assert "orders" in stg["inputs"]


def test_lineage_mermaid_smoke():
    m = format_lineage_mermaid()
    assert "flowchart TB" in m
    assert "-->|" in m
