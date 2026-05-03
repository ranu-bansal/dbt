# dbt documentation — why it looks “empty” and how to fix it

## Lineage as a graph (two options)

| View | What you see | How |
|------|----------------|-----|
| **Pipeline-level** (Airflow-style: datasets + job names on arrows) | `config/pipelines/*.yaml` | `python run.py --lineage-write` → open **`docs/lineage_graph.html`** in a browser, or view **`docs/LINEAGE.md`** (Mermaid) in GitHub / VS Code |
| **Model-level** (dbt DAG: `source` / `ref`) | dbt project | `python run.py --docs-serve` → Lineage tab in the dbt docs site |

They complement each other: pipelines show *orchestration* naming; dbt shows *SQL dependency* detail.

## Run history (runtime in docs)

**`docs/RUN_HISTORY.md`** lists the last **10** pipeline runs with **duration (seconds)** from `runs/runs.json` (end-to-end per pipeline, not per SQL).

Refresh after runs:

```bash
python run.py --runs-write      # last 10 only
python run.py --runs-write 20   # last 20
python run.py --docs-write      # lineage files + RUN_HISTORY together
```

Older runs may show `—` for runtime if they were logged before `duration_seconds` was added.

### Run history inside `dbt docs serve`

`python run.py --docs` / `--docs-serve` **refreshes** `dbt_project/docs/pipeline_runs.md` from `runs/runs.json` before generating the site. In the browser, open **Analysis** → **`pipeline_runs`** — the description panel shows the same table (runtime, status, timestamps).

`docs/RUN_HISTORY.md` at repo root is the same content for GitHub / offline reading.

## 1. **Wrong database → no types / thin schema tab**

`profiles.yml` uses:

```yaml
path: "{{ env_var('QUINCE_DUCKDB_PATH', ':memory:') }}"
```

If **`QUINCE_DUCKDB_PATH` is not set**, dbt connects to **`:memory:`** when you run `dbt docs generate`. That database has **no tables**, so **`catalog.json`** has almost no column types — the docs site looks broken or minimal.

**Fix — always set both env vars from `dbt_project/`:**

```bash
cd dbt_project
export QUINCE_DUCKDB_PATH="$(cd .. && pwd)/data/warehouse.duckdb"
export DBT_PROFILES_DIR="$(pwd)"
```

## 2. **Warehouse not built yet**

`catalog.json` is built by **introspecting** `data/warehouse.duckdb`. That file gets **raw** tables when you run **any** pipeline (`python run.py …`). It gets **models** (views) after **`dbt run`** (also triggered by the same pipelines).

If `warehouse.duckdb` doesn’t exist or is old, run once:

```bash
cd /path/to/quince_demo
python run.py orders_enriched
```

Or from the **repo root** (sets env for you):

```bash
python run.py --docs          # dbt docs generate
python run.py --docs-serve    # generate + dbt docs serve
```

Or manually:

```bash
cd dbt_project
export QUINCE_DUCKDB_PATH="$(cd .. && pwd)/data/warehouse.duckdb"
export DBT_PROFILES_DIR="$(pwd)"
dbt docs generate
dbt docs serve
```

## 3. **Human-readable text = YAML `description`**

- **Column types** in the UI come from the **catalog** (DB introspection).
- **Paragraphs / column blurbs** come from **`description:`** in:
  - `models/**/schema.yml` (models + columns)
  - `models/sources.yml` (sources + tables + columns)

If you only define tests and no descriptions, you’ll see **types and tests** but **little narrative**. Add `description:` where you want richer docs.

## 4. **Quick check**

After `dbt docs generate`, open `dbt_project/target/catalog.json`. If `"nodes": {}` and `"sources": {}` are empty, the DB path was wrong or the warehouse was empty.
