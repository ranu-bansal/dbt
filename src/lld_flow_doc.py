"""Markdown fragment: LLD orchestrator flow for generated docs (RUN_HISTORY, dbt Docs)."""

# Mermaid: GitHub/VS Code render; dbt Docs may show as a fenced code block.
_LLD_MERMAID = """
```mermaid
flowchart LR
  A[run.py] --> B[Pipeline YAML]
  B --> C[load_raw_into_duckdb]
  C --> D[dbt run model+]
  D --> E[dbt test model]
  E --> F[Export CSV]
  F --> G[runs.json]
```
"""


def format_lld_flow_markdown() -> str:
    """
    Self-contained LLD section for embedding in generated Markdown files.
    Keep in sync with docs/LLD.md (high level).
    """
    lines = [
        "## LLD: Orchestrator flow (reference)",
        "",
        "End-to-end steps for a single pipeline run (`python run.py <pipeline>`).",
        "For **`--all`**, pipelines run in **topological order** from `config/pipelines/*.yaml` inputs (`pipeline_run_order`).",
        "",
        "### Module call chain",
        "",
        "`run.py` → `orchestrator.run_pipeline` → `dbt_run.run_dbt_pipeline` → `dbt_loader.load_raw_into_duckdb` + subprocess **dbt** → pandas export → `run_log.append_run`.",
        "",
        "### Control flow (diagram)",
        "",
        _LLD_MERMAID.strip(),
        "",
        "### Ordered steps",
        "",
        "1. **Resolve config** — `config/pipelines/<name>.yaml` (`transform.model`, `output`).",
        "2. **Load raw** — `registry.yaml` → `CREATE OR REPLACE raw.*` in `warehouse.duckdb`.",
        "3. **dbt run** — `dbt run --select <model>+` (builds model + upstream refs in selection).",
        "4. **dbt test** — `dbt test --select <model>`.",
        "5. **Export** — `SELECT *` from `main_staging` / `main_marts` for that model → CSV.",
        "6. **Publish** — `data/curated/<output>/<run_id>.csv` and `latest.csv`.",
        "7. **Log** — append to `runs/runs.json` (status, duration, `validation_summary`).",
        "",
        "Full LLD (interfaces, data contracts): **`docs/LLD.md`**. **Interview diagrams** (many figures + talking points): **`docs/LLD_INTERVIEW.md`**.",
        "",
    ]
    return "\n".join(lines)
