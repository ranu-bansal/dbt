"""Build lineage from pipeline configs: upstream (inputs) and downstream (consumers)."""
from pathlib import Path
from typing import Any

from .registry import get_project_root
from .pipeline_config import load_pipeline_config


def _load_all_pipelines(project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load all pipeline configs from config/pipelines/*.yaml."""
    root = project_root or get_project_root()
    pipelines_dir = root / "config" / "pipelines"
    if not pipelines_dir.exists():
        return {}
    result = {}
    for f in sorted(pipelines_dir.glob("*.yaml")):
        name = f.stem
        try:
            result[name] = load_pipeline_config(name, root)
        except Exception:
            pass
    return result


def build_lineage_graph(project_root: Path | None = None) -> dict[str, Any]:
    """
    Build lineage graph from pipeline configs.
    Returns:
      pipelines: { name: { inputs: [...], output: str } }
      datasets: { name: { produced_by: pipeline_name | None, consumed_by: [pipeline_names] } }
    """
    root = project_root or get_project_root()
    pipelines = _load_all_pipelines(root)
    pipelines_info = {}
    datasets_info: dict[str, dict[str, Any]] = {}

    for pname, config in pipelines.items():
        inputs = config.get("inputs", [])
        output = config.get("output", pname)
        pipelines_info[pname] = {"inputs": inputs, "output": output}
        for d in inputs:
            if d not in datasets_info:
                datasets_info[d] = {"produced_by": None, "consumed_by": []}
            datasets_info[d]["consumed_by"].append(pname)
        if output not in datasets_info:
            datasets_info[output] = {"produced_by": None, "consumed_by": []}
        datasets_info[output]["produced_by"] = pname

    return {"pipelines": pipelines_info, "datasets": datasets_info}


def get_lineage(name: str, project_root: Path | None = None) -> dict[str, Any] | None:
    """
    Get upstream (inputs) and downstream (consumers) for a pipeline or dataset.
    Returns dict with: type, upstream, downstream, or None if not found.
    """
    graph = build_lineage_graph(project_root)
    pipelines = graph["pipelines"]
    datasets = graph["datasets"]

    if name in pipelines:
        info = pipelines[name]
        out = info.get("output")
        downstream = list(datasets.get(out, {}).get("consumed_by", [])) if out else []
        return {
            "type": "pipeline",
            "name": name,
            "upstream": info.get("inputs", []),
            "downstream": downstream,
            "output": out,
        }

    if name in datasets:
        info = datasets[name]
        return {
            "type": "dataset",
            "name": name,
            "upstream": [info["produced_by"]] if info["produced_by"] else [],
            "downstream": info.get("consumed_by", []),
            "produced_by": info["produced_by"],
        }

    return None


def format_lineage(name: str, project_root: Path | None = None) -> str:
    """Format lineage for a pipeline or dataset as readable text."""
    line = get_lineage(name, project_root)
    if line is None:
        return f"Unknown pipeline or dataset: {name}"
    lines = [f"Lineage: {line['name']} ({line['type']})", ""]
    if line["type"] == "pipeline":
        lines.append(f"  Output dataset: {line.get('output', '—')}")
    else:
        lines.append(f"  Produced by pipeline: {line.get('produced_by') or '—'}")
    lines.append("  Upstream (inputs):")
    for u in line.get("upstream", []) or ["(none)"]:
        lines.append(f"    - {u}")
    lines.append("  Downstream (consumers):")
    for d in line.get("downstream", []) or ["(none)"]:
        lines.append(f"    - {d}")
    return "\n".join(lines)


def format_full_graph(project_root: Path | None = None) -> str:
    """Format full lineage graph as text (pipeline -> output, pipeline -> inputs)."""
    graph = build_lineage_graph(project_root)
    lines = ["Lineage graph", "=============", ""]
    for pname, info in graph["pipelines"].items():
        out = info.get("output", "")
        inputs = ", ".join(info.get("inputs", []))
        lines.append(f"  {pname}")
        lines.append(f"    inputs:  {inputs}")
        lines.append(f"    output:  {out}")
        lines.append("")
    return "\n".join(lines)


def _mermaid_node_id(name: str) -> str:
    """Stable Mermaid node id (avoid reserved words / special chars)."""
    slug = "".join(c if c.isalnum() else "_" for c in name)
    return f"n_{slug}"


def format_lineage_mermaid(project_root: Path | None = None) -> str:
    """
    Mermaid flowchart: dataset nodes, edges labeled with pipeline name (Airflow-style flow).
    Renders in GitHub, GitLab, VS Code Markdown preview, etc.
    """
    graph = build_lineage_graph(project_root)
    datasets: set[str] = set()
    for _, info in graph["pipelines"].items():
        for i in info.get("inputs", []):
            datasets.add(i)
        o = info.get("output", "")
        if o:
            datasets.add(o)

    raw_datasets: set[str] = set()
    try:
        from .registry import load_registry

        reg = load_registry(project_root)
        for dname, meta in reg.get("datasets", {}).items():
            if meta.get("type") == "raw":
                raw_datasets.add(dname)
    except Exception:
        pass

    body: list[str] = [
        "flowchart TB",
        "",
        "    classDef raw fill:#e1f5fe,stroke:#01579b;",
        "    classDef curated fill:#e8f5e9,stroke:#1b5e20;",
        "",
    ]
    for d in sorted(datasets):
        nid = _mermaid_node_id(d)
        body.append(f'    {nid}["{d}"]')
        body.append(f"    class {nid} {'raw' if d in raw_datasets else 'curated'}")
    body.append("")
    for pname, info in sorted(graph["pipelines"].items()):
        out = info.get("output", "")
        if not out:
            continue
        oid = _mermaid_node_id(out)
        for inp in info.get("inputs", []):
            iid = _mermaid_node_id(inp)
            body.append(f"    {iid} -->|{pname}| {oid}")
    return "\n".join(body)


def lineage_mermaid_markdown(project_root: Path | None = None) -> str:
    """Markdown snippet with fenced Mermaid block."""
    inner = format_lineage_mermaid(project_root)
    header = (
        "# Pipeline lineage (graph)\n\n"
        "Generated from `config/pipelines/*.yaml`. "
        "Edges show **which pipeline** moves data from input dataset → output dataset.\n\n"
        "Re-generate: `python run.py --lineage-write`\n\n"
    )
    return header + "```mermaid\n" + inner + "\n```\n"


def write_lineage_docs(project_root: Path | None = None) -> Path:
    """Write docs/LINEAGE.md (Mermaid)."""
    root = project_root or get_project_root()
    path = root / "docs" / "LINEAGE.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lineage_mermaid_markdown(root))
    return path


def write_lineage_html(project_root: Path | None = None) -> Path:
    """Write docs/lineage_graph.html (Mermaid.js in browser, no server)."""
    root = project_root or get_project_root()
    inner = format_lineage_mermaid(root)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Quince ETL — lineage</title>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
  </script>
  <style>body {{ font-family: system-ui, sans-serif; margin: 1rem; }}</style>
</head>
<body>
  <h1>Pipeline lineage</h1>
  <p>From config pipelines (same graph as <code>docs/LINEAGE.md</code>). Refresh after <code>python run.py --lineage-write</code>.</p>
  <pre class="mermaid">
{inner}
  </pre>
</body>
</html>
"""
    path = root / "docs" / "lineage_graph.html"
    path.write_text(html)
    return path
