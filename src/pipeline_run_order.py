"""Topological order of pipelines from config (input datasets produced by other pipelines)."""
from pathlib import Path

from .lineage import build_lineage_graph


def topological_sort_pipelines(project_root: Path | None = None) -> list[str]:
    """
    Order pipeline names so every producer runs before consumers.

    An edge P -> Q exists when Q lists an input dataset that P produces
    (from lineage: datasets[input].produced_by == P).
    Raw-only inputs (no producer pipeline) add no edge.
    """
    graph = build_lineage_graph(project_root)
    pipelines = list(graph["pipelines"].keys())
    datasets = graph["datasets"]

    from collections import defaultdict

    adj: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {p: 0 for p in pipelines}

    for pname in pipelines:
        info = graph["pipelines"][pname]
        for inp in info.get("inputs", []):
            prod = datasets.get(inp, {}).get("produced_by")
            if prod and prod in graph["pipelines"] and prod != pname:
                adj[prod].append(pname)
                indegree[pname] += 1

    for k in adj:
        adj[k].sort()

    order: list[str] = []
    done: set[str] = set()

    while len(done) < len(pipelines):
        ready = sorted(p for p in pipelines if indegree[p] == 0 and p not in done)
        if not ready:
            raise ValueError(
                "Cycle detected in pipeline dependencies. Check config/pipelines/*.yaml inputs vs outputs."
            )
        u = ready[0]
        done.add(u)
        order.append(u)
        for v in adj[u]:
            indegree[v] -= 1

    return order
