# Quince Self-Serve ETL (Hybrid: Custom + dbt)

The **custom layer** loads raw CSVs into DuckDB and handles run log + CSV publish; **dbt** runs models and schema tests. Each run writes `data/curated/<output>/<run_id>.csv` and `latest.csv`, and appends to `runs/runs.json`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv/Scripts/activate on Windows
pip install -r requirements.txt
```

## Run

```bash
python run.py stg_orders
python run.py orders_enriched
python run.py sales_by_brand_country

# Run every pipeline once, in dependency order (e.g. stg_orders before orders_enriched)
python run.py --all
```

## CLI

- `python run.py <pipeline_name>` — run a pipeline
- `python run.py --list` — list pipelines
- `python run.py --runs [N]` — list last N runs (default 10)
- `python run.py --run <run_id>` — show full run log
- `python run.py --lineage` — full lineage (text)
- `python run.py --lineage <pipeline_or_dataset>` — upstream / downstream
- `python run.py --lineage-graph` — **Mermaid** diagram (Airflow-style: datasets + pipeline labels on edges) — paste into Notion, or use below
- `python run.py --lineage-write` — writes **`docs/LINEAGE.md`** and **`docs/lineage_graph.html`** (open HTML in a browser for an interactive graph)
- **dbt docs** (`python run.py --docs-serve`) also shows a **model-level** DAG (sources → `ref()`), separate from pipeline-level graph above
- **`docs/RUN_HISTORY.md`** — last 10 pipeline runs with **runtime (seconds)** plus an **LLD orchestrator flow** (Mermaid + steps) for sharing (regenerate: `python run.py --runs-write` or `python run.py --docs-write` for lineage + run history)
- **`dbt docs serve`** — the same run table and **LLD flow** are embedded: open **Analysis** → **`pipeline_runs`** and read the **Description** (refreshed when you run `python run.py --docs` or `--docs-serve`)
- `python run.py --docs` — `dbt docs generate` (sets `QUINCE_DUCKDB_PATH` automatically)
- `python run.py --docs-serve` — generate + `dbt docs serve`
- dbt run --full-refresh --select sales_by_brand_country


## Architecture docs

- **`docs/LLD_INTERVIEW.md`** — **detailed LLD diagrams** (Mermaid) + interview talking points — export to PNG/SVG from [mermaid.live](https://mermaid.live) for slides.
- **`docs/LLD.md`** — full low-level design (text + contracts).
- **`docs/HLD_LLD.md`** — HLD + LLD overview.

## dbt docs (lineage + schema types + descriptions)

**Both env vars are required.** If `QUINCE_DUCKDB_PATH` is missing, the profile defaults to `:memory:` and **`dbt docs generate` produces an empty catalog** (no column types in the UI).

```bash
# 1) Build warehouse (raw + models) at least once
python run.py orders_enriched

# 2) Generate and serve docs (from repo root)
cd dbt_project
export QUINCE_DUCKDB_PATH="$(cd .. && pwd)/data/warehouse.duckdb"
export DBT_PROFILES_DIR="$(pwd)"
dbt docs generate
dbt docs serve
```

Narrative text in the docs UI comes from **`description:`** in `dbt_project/models/**/schema.yml` and `sources.yml`. See **`docs/DBT_DOCS.md`** for troubleshooting.

## Add a new pipeline

1. Register raw datasets in `config/registry.yaml` (`type: raw`).
2. Add a dbt model under `dbt_project/models/` with `ref()` / `source('raw', ...)`. Add tests in `schema.yml`.
3. Add `config/pipelines/<name>.yaml` with `transform.type: dbt` and `transform.model`.
4. Run `python run.py <name>`.

SQL lives in **`dbt_project/models/`** only (no duplicate `sql/` folder).

## Tests

```bash
pytest tests/ -q
```


python run.py --docs-serve

# Duckdb
brew install duckdb
duckdb data/warehouse.duckdb

show databases;
show all tables;
select * from raw.order_items;
select * from '/Users/RANU/PycharmProjects/quince_demo/data/raw/customers.csv';


cd /Users/RANU/PycharmProjects/quince_demo
export QUINCE_DUCKDB_PATH="$(pwd)/data/warehouse.duckdb"
export DBT_PROFILES_DIR="$(pwd)/dbt_project"
dbt run --full-refresh --select sales_by_brand_country --project-dir dbt_project