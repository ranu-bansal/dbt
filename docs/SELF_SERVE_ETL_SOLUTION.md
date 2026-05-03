# Self-Serve ETL Platform — Solution Document

## 1. Executive Summary

**Problem:** Data Engineering at Quince is a bottleneck. Multiple teams need new datasets for reporting, experimentation, and operations, but depend on DE for every pipeline.

**Solution:** A self-serve ETL framework where internal teams define and run simple transformations with built-in guardrails for quality, consistency, and reliability—without needing DE for every request.

**Design principles:**
- **Declarative over imperative:** Users define *what* (sources, transforms, checks) in config; the platform runs *how*.
- **Guardrails by default:** Schema, quality, and observability are first-class; bad data is caught before publish.
- **Progressive adoption:** Start with local/minimal, scale to production without rewriting user definitions.

---

## 2. Platform Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SELF-SERVE ETL PLATFORM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Registry    │  │  Transform   │  │  Validation  │  │  Scheduler   │     │
│  │  (datasets,  │  │  Engine      │  │  Engine      │  │  (cron/      │     │
│  │   schemas)   │  │  (SQL/pandas)│  │  (DQ rules)  │  │   triggers)  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │             │
│         └─────────────────┴────────┬────────┴─────────────────┘             │
│                                    ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     ORCHESTRATOR / RUNNER                             │   │
│  │  Load config → Resolve inputs → Run transform → Run DQ → Publish      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌─────────────────────────────────┼─────────────────────────────────────┐   │
│  │  OBSERVABILITY                   │  STORAGE                            │   │
│  │  Run logs, status, metrics       │  Raw (inputs) / Curated (outputs)   │   │
│  └─────────────────────────────────┴─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Main Components

| Component | Responsibility |
|-----------|----------------|
| **Registry** | Catalog of datasets (raw + curated), schemas, lineage. Single source of truth for “what exists.” |
| **Transform Engine** | Executes user-defined transforms (SQL or Python/pandas). Reads from registered inputs, writes to staging then curated on success. |
| **Validation Engine** | Runs data quality rules (nulls, uniqueness, thresholds, accepted values). Blocks publish if critical checks fail. |
| **Scheduler** | Triggers runs by schedule or event. In local version: CLI/manual; in production: cron, Airflow, or event-driven. |
| **Orchestrator** | One run = load pipeline config → resolve inputs → transform → validate → publish (or fail with clear log). |
| **Observability** | Run IDs, status (success/failed), run log (stdout + check results), optional metrics. |

### How They Interact

1. **User** registers a dataset (or uses existing raw datasets) and creates a **pipeline config** (YAML/JSON): inputs, transform type/params, validation rules, output dataset.
2. **Orchestrator** loads the config, asks **Registry** for input schemas/locations.
3. **Transform Engine** reads raw data, applies the transformation, writes to a **staging** output.
4. **Validation Engine** runs DQ rules on the staging output. Results are recorded.
5. If all critical checks pass → output is **published** (moved/copied to curated path and registered). If not → publish is skipped, run marked failed, log explains which checks failed.
6. **Observability** records run_id, status, timestamps, and run log (including validation results) for every run.

---

## 3. User Workflows

### 3.1 Register a New Dataset

**Purpose:** Make a raw or curated dataset discoverable and enforce schema.

**Flow:**
1. User adds a **dataset registration** (file or API): name, type (raw/curated), path/URI, and **schema** (column names, types, optional constraints).
2. Registry stores this and validates that the schema file is valid.
3. Optionally: a one-off “snapshot” run can validate that the file at the path matches the declared schema.

**Local implementation:**  
A `registry.yaml` (or `registry/` folder with one YAML per dataset) plus a small Python API to read/validate. Paths are local (e.g. `data/raw/orders.csv`).

### 3.2 Define a Transformation

**Purpose:** Specify how to go from one or more inputs to one output.

**Flow:**
1. User creates a **pipeline** config (e.g. `pipelines/orders_enriched.yaml`).
2. Config specifies:
   - **inputs:** list of registered dataset names or paths.
   - **transform:** type (e.g. `sql`, `python`, `join`) and the definition (SQL query, Python module + function name, or join keys + columns).
3. Transform runs in a sandbox: only the declared inputs are visible; output schema is inferred or declared.

**Local implementation:**  
- **SQL:** Use DuckDB (or SQLite) to run a single SQL file or inline query against loaded tables.  
- **Python:** One module per pipeline, one entrypoint function `transform(raw_dfs: dict) -> DataFrame`; platform passes a dict of input name → DataFrame.

### 3.3 Configure Validation Rules

**Purpose:** Ensure only valid data is published.

**Flow:**
1. In the same pipeline config (or a separate validation config), user defines **validation rules** per output (or per table).
2. Rule types (examples):
   - **null_check:** column(s), severity (critical/warning).
   - **uniqueness:** column(s) or key.
   - **row_count:** min/max or range.
   - **accepted_values:** column + allowed set (or regex).
3. Each rule has a **severity.** Critical failures block publish; warnings are logged but do not block.

**Local implementation:**  
A small DQ runner that takes a DataFrame and a list of rules, runs them, returns pass/fail per rule and a summary. Orchestrator uses this to decide publish vs fail.

### 3.4 Publish Output

**Purpose:** Make the curated dataset available and auditable.

**Flow:**
1. After transform and validation success, the **publish** step:
   - Copies/moves the staging output to the **curated** path (e.g. `data/curated/<dataset_name>/<run_id>.parquet` or `latest.parquet`).
   - Updates Registry with the new output location and optional schema.
   - Records run status as **success** and what was published where.
2. If validation fails, publish is skipped, run status is **failed**, and the run log lists failed checks.

**Local implementation:**  
Write to `data/curated/<name>/` with a timestamp or run_id in the filename; append a line to a `run_log.csv` or `runs.json` with run_id, status, timestamp, and path.

---

## 4. Enforcement Mechanisms

### 4.1 Schema Consistency

- **Registry:** Every dataset has a declared schema (column names + types). Transforms that produce a new dataset can declare an **output schema** in the pipeline config.
- **Validation:** Before or after transform, the platform can check that the actual columns and types match the declared schema (e.g. with pandas dtypes or DuckDB `DESCRIBE`).
- **Single source of truth:** Pipeline configs reference dataset **names** from the Registry; paths and schemas are resolved from there, reducing ad-hoc paths and schema drift.

### 4.2 Data Quality Checks

- **Declarative rules:** All checks are defined in config (no one-off scripts). Same rule types (null, uniqueness, row count, accepted values) for every pipeline.
- **Severity:** Critical vs warning. Only critical failures block publish.
- **Run log:** Every run records which rules passed/failed and, if possible, row counts or sample failures, so teams can fix data or relax rules in a controlled way.

### 4.3 Observability

- **Run ID:** Every run has a unique ID (e.g. UUID or timestamp-based).
- **Status:** success / failed (and optionally running).
- **Run log:** Stored in a known place (e.g. `logs/runs.json` or a `run_log` table): run_id, pipeline_id, status, start_ts, end_ts, error message if failed, and validation summary (which checks failed).
- **Visibility:** CLI or simple UI can list recent runs and show log for a given run_id. No need for heavy infra at MVP.

### 4.4 Reusability / Standards

- **Templates:** Standard pipeline template (inputs → transform → validation → output) so every team follows the same pattern.
- **Shared rules:** Common validation rule definitions (e.g. “no nulls in key columns”) can be stored as named rule sets and included in pipelines by name.
- **Conventions:** Naming (e.g. `raw_*`, `curated_*`), directory layout (`data/raw/`, `data/curated/`), and config layout (e.g. `pipelines/<name>.yaml`) so the platform and docs are consistent.

---

## 5. Using dbt: Pros and Cons

**dbt (data build tool)** is a strong fit for the *transform + test* part of a self-serve ETL platform. It is SQL-centric, runs against a database (or DuckDB locally), and has built-in testing and documentation.

### Pros of using dbt

| Benefit | Why it helps |
|--------|----------------|
| **Transform as SQL models** | Teams define transformations as SQL; `ref()` gives automatic lineage and execution order. No custom DAG code. |
| **Built-in data quality** | Schema tests: `unique`, `not_null`, `accepted_values`, `relationships`; custom tests (SQL or Python); severity (error/warn). Matches “null validation, uniqueness, accepted values” from the case study. |
| **Documentation and lineage** | `dbt docs generate` gives a DAG and column-level lineage. Good for “visibility” and onboarding. |
| **Local runs with DuckDB** | **dbt-duckdb** adapter lets you run dbt locally against DuckDB; you can load 2–3 raw CSVs as sources and build models. Fits “local laptop” constraint. |
| **Widely adopted** | Many teams already know dbt; hiring and patterns are easier. |
| **Reusability** | Macros, packages, and a standard project layout encourage consistent patterns. |
| **Run visibility** | `dbt run` and `dbt test` produce clear success/fail and run artifacts (e.g. `run_results.json`), which you can use for “run log / status output.” |

### Cons and considerations

| Drawback | Mitigation |
|----------|------------|
| **SQL-first** | Case study allows “configurable transformation” (SQL or Python). dbt is primarily SQL; Python models exist but are secondary. If many pipelines need complex Python, you may add a thin “Python transform” layer alongside dbt or use dbt Python models. |
| **Requires a database** | dbt runs against a DB. For “read 2–3 raw CSV/Parquet files,” you load them into DuckDB first (e.g. via dbt-duckdb external tables or a small loader script). One-time setup per pipeline. |
| **No built-in scheduler** | dbt does not schedule; you run `dbt run && dbt test` via CLI, cron, or Airflow. For the exercise, CLI is enough; for production, you add scheduling outside dbt. |
| **Registry is separate** | “Register a dataset” is not native dbt. You still need a lightweight registry (YAML or DB) for raw paths/schemas and to map “curated” outputs to locations; dbt handles the transform and test steps. |
| **Publish semantics** | dbt writes to the target database/schema. “Publish” might mean “run succeeded and tests passed”; if you need a physical “curated” file (e.g. Parquet export), add a post-step (e.g. `COPY TO` or a small export script). |

### Verdict

- **Use dbt** if: Transformations are mostly SQL, you want standard DQ tests and lineage with minimal custom code, and you’re fine with DuckDB (or another DB) as the execution engine locally.
- **Use a custom engine** (e.g. pandas + YAML) if: You want to avoid dbt’s learning curve, need heavy Python transforms, or want “just CSV in → CSV out” with no DB.

**Hybrid option:** Use dbt for SQL pipelines and shared tests; keep a small custom layer for registry, raw-file loading into DuckDB, and run log aggregation. That gives you dbt’s strengths while still satisfying “register dataset,” “publish,” and “run log” in one platform.

### The hybrid approach in detail

In the hybrid, the platform is split into **two layers** that run in sequence:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  CUSTOM LAYER (Python)                    │  DBT LAYER                           │
│  • Registry (YAML): dataset name → path   │  • Sources: point at DuckDB tables   │
│  • Load raw files → DuckDB (staging)      │  • Models: SQL transforms (ref())     │
│  • Run log: run_id, status, timestamps    │  • Tests: unique, not_null, etc.     │
│  • Publish: export curated table → file   │  • run_results.json → feed run log   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**1. What the custom layer does**

| Responsibility | How |
|----------------|-----|
| **Registry** | YAML (or DB) listing datasets: name, path (e.g. `data/raw/orders.csv`), optional schema. Single place to “register” raw and curated datasets. |
| **Load raw into DuckDB** | Before dbt runs: read paths from registry, load 2–3 CSVs/Parquet into DuckDB tables (e.g. `raw.orders`, `raw.customers`). dbt then sees them as **sources**. |
| **Orchestration** | One entrypoint (e.g. `python run.py <pipeline>` or `python run.py --all`): (1) load config and registry, (2) load raw → DuckDB, (3) invoke `dbt run && dbt test`, (4) read dbt run/test results, (5) export curated table to file if success, (6) write run log (run_id, status, dbt summary). |
| **Publish (file output)** | If dbt run + test succeed: export the final dbt model from DuckDB to `data/curated/<name>/<run_id>.parquet` (e.g. via `COPY TO` or pandas). Optional: update registry with new curated path. |
| **Run log** | Append each run to `runs.json` or similar: run_id, pipeline, status (success/failed), start/end time, which dbt models/tests failed (from `run_results.json`), and path to curated file if published. |

**2. What dbt does**

| Responsibility | How |
|----------------|-----|
| **Transform** | SQL models in `models/`; `ref()` for dependencies. Raw tables are `source()`; staging and marts are `ref()`. dbt run builds the DAG and executes. |
| **Data quality** | Schema and custom tests in `schema.yml` (unique, not_null, accepted_values, row count via custom test). Failures surface in `run_results.json`. |
| **Lineage and docs** | `dbt docs generate` for DAG and column lineage. |

**3. End-to-end flow (one pipeline run)**

1. User runs: `python run.py orders_enriched` (or a wrapper that calls this).
2. **Custom:** Load `registry.yaml` and pipeline config for `orders_enriched`; get paths for raw inputs (e.g. `orders.csv`, `customers.csv`).
3. **Custom:** Create/connect DuckDB; load those files into `raw.orders`, `raw.customers`.
4. **Custom:** Optionally set dbt vars or override source paths so dbt uses this DuckDB.
5. **Custom:** Run `dbt run --select orders_enriched` (and its upstream models) and `dbt test --select orders_enriched`.
6. **Custom:** Read `target/run_results.json` (and test results). If any critical model or test failed → set status = failed, write run log, stop (no publish).
7. **Custom:** If success: export the `orders_enriched` table from DuckDB to `data/curated/orders_enriched/<run_id>.parquet`; write run log with status = success and path.
8. User (or a UI) can list runs and inspect run log for visibility.

**4. Directory layout (hybrid)**

```
quince_demo/
├── config/
│   └── registry.yaml              # dataset name → path, schema (custom)
├── data/
│   ├── raw/                       # raw CSVs/Parquet (paths in registry)
│   └── curated/                  # published Parquet (custom export)
├── dbt_project/
│   ├── dbt_project.yml
│   ├── profiles.yml               # DuckDB connection
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_orders.sql     # select from source('raw','orders')
│   │   ├── marts/
│   │   │   └── orders_enriched.sql # ref('stg_orders'), etc.
│   │   └── schema.yml             # tests on models
│   └── target/
│       └── run_results.json       # consumed by custom layer
├── runs/
│   └── runs.json                  # run log (custom)
├── run.py                         # orchestrator: load → dbt run/test → publish → log
└── requirements.txt               # dbt-duckdb, duckdb, pyyaml, etc.
```

**5. When to use dbt vs custom in the hybrid**

- **Use dbt:** All SQL-based pipelines (joins, aggregations, filters). All standard and custom tests (nulls, uniqueness, accepted values, row counts). Lineage and docs.
- **Use custom only:** Registry, loading raw files into DuckDB, orchestration order, publishing to files, and run log. Optional: a separate “Python pipeline” path for teams that need pandas-only transforms (custom layer runs Python, skips dbt for that pipeline).

**6. Summary**

The hybrid keeps “register dataset,” “publish,” and “run log” in one place (custom layer) while using dbt for transforms and data quality. Same registry and run log work for both dbt and non-dbt pipelines if you add a Python-only path later.

---

## 6. Scaling from Laptop to Production

| Aspect | Local (Laptop) | Production |
|--------|----------------|------------|
| **Storage** | Local CSV/Parquet in `data/raw`, `data/curated` | S3/GCS + optional data lake (Iceberg/Hudi) or warehouse (Snowflake/BigQuery) |
| **Compute** | Single process, pandas or DuckDB | Distributed (Spark, Dask) or warehouse SQL; same pipeline *config* can map to different execution backends |
| **Scheduling** | CLI: `python -m etl run pipeline_name` | Cron, Airflow, or event-driven (e.g. “run when raw file lands”) |
| **Registry** | YAML files in repo | DB or object store + API; same schema for dataset metadata |
| **Secrets** | Env vars or local file | Secret manager (e.g. AWS Secrets Manager) |
| **Observability** | Local run log file / JSON | Log aggregation + metrics (e.g. Prometheus) + optional UI (e.g. React app reading run API) |

**Key idea:** Keep pipeline definitions (inputs, transform, validation, output name) **backend-agnostic**. The same YAML works locally; in production a different “runner” (e.g. Airflow operator or K8s job) reads that YAML and runs it on the appropriate engine (Spark, Snowflake, etc.). Only paths and execution environment change.

---

## 7. What We Can vs Cannot Implement (Implementability Checklist)

### 7.1 What we CAN implement (no red flags)

All of the following are achievable in the **minimal local version** (Python, DuckDB/pandas, local files, no cloud/orchestrator):

| Area | What | How |
|------|------|-----|
| **Registry** | Register datasets (name, path, schema) | YAML + Python loader; paths point to `data/raw/*.csv` or `.parquet`. |
| **Read 2–3 raw inputs** | Load multiple raw files | pandas `read_csv`/`read_parquet` or DuckDB `read_csv_auto`; paths from registry. |
| **Configurable transform** | One transformation per pipeline | SQL (DuckDB) or Python (pandas) selected via pipeline YAML; single output DataFrame/table. |
| **Data quality checks** | Null, uniqueness, row count, accepted values | Python validation engine: run rules on DataFrame, return pass/fail per rule with severity. |
| **Severity (critical vs warning)** | Block publish on critical failure only | Config per rule; orchestrator only blocks publish if any critical check fails. |
| **Write curated output** | One curated dataset per run | Write DataFrame to `data/curated/<name>/<run_id>.parquet` (or CSV). |
| **Run log / status** | Run ID, status, timestamps, which checks failed | Append each run to `runs.json` (or CSV); print summary to stdout. |
| **Visibility** | List runs, show run log for a run | CLI or small script: read `runs.json`, filter by pipeline/date, print run_id and status. |
| **Schema consistency** | Optional check that output matches declared schema | Compare DataFrame dtypes/columns to registry or pipeline output schema; fail or warn. |
| **Reusability** | Shared validation rule sets, one pipeline template | YAML anchors or include files; one standard pipeline schema. |
| **dbt hybrid (optional)** | Use dbt for SQL + tests, custom for rest | Custom: registry, load raw → DuckDB, run dbt, export result, run log. dbt: models + tests. |

Nothing in the **code exercise requirements** or the **solution design** requires AWS, Airflow, Kubernetes, or external infra for the minimal version.

### 7.2 Red flags: what we CANNOT implement (or only document)

These are **out of scope** or **forbidden** for the local exercise; we can design for them and document, but not build:

| Item | Why we can’t implement (local) |
|------|--------------------------------|
| **AWS / GCP / cloud storage** | Exercise explicitly says “Do not require AWS”; no S3, Lambda, etc. |
| **Airflow / orchestration engine** | “Do not require … Airflow”; scheduling = CLI or cron script only. |
| **Kubernetes / containers** | “Do not require … Kubernetes”; single process on laptop. |
| **Managed DB or external DB** | Only DuckDB/SQLite/local files; no RDS, Snowflake, BigQuery as runtime. |
| **Real-time / streaming** | Case study is “simple data transformations” and “scheduling”; batch only. No Kafka, Flink, etc. |
| **Multi-tenant / RBAC / auth** | Not in scope for minimal version; no user auth or permission checks. |
| **Distributed compute (Spark cluster)** | Local = single machine; Spark local mode is OK if we want, but no cluster. |

We **can** document how production would use cloud, Airflow, K8s, etc., and keep pipeline configs backend-agnostic so they could be reused later.

### 7.3 Partially implement or “stub”

| Item | What we can do | What we don’t do |
|------|----------------|------------------|
| **Scheduling** | Implement a CLI (`run.py <pipeline>`) and a small script or docs for running via cron. | No built-in scheduler daemon or UI. |
| **Observability** | Run log (JSON) + optional “list runs” / “show run” CLI. | No Prometheus, Grafana, or run-history UI. |
| **Publish “to production”** | Write to `data/curated/` and optionally update registry with path. | No promotion workflow, versioning, or approval gates. |
| **Scale to production** | Document scaling path (storage, compute, scheduler, secrets). | No actual deployment to cloud or K8s. |

### 7.5 Requirement coverage: dependency, docs, freshness, metadata, naming, macros, observability, tests

| Requirement | Handled? | How | Flag if not |
|-------------|----------|-----|--------------|
| **Dependency of table/query** | Yes | Pipeline config `inputs` = upstream datasets; transform (SQL/Python) defines query-level deps. With dbt: `ref()`/`source()` give full DAG. | — |
| **Documentation** | Yes | Registry can store `description` per dataset; pipeline config can have `description`. Optional: doc generator from registry + config → Markdown/HTML. | — |
| **Dependency view** | Yes | Build graph from registry + pipeline configs (inputs → output). Script or dbt `docs generate` to expose DAG (e.g. JSON + simple viz or dbt docs UI). | — |
| **Freshness** | Partial | **Last run time:** from run log (run_id, pipeline, timestamp). **Expected freshness / SLA:** not in base design. | **Flag:** Add `max_age_hours` (or similar) in pipeline/registry and a check that fails or warns if data is stale. |
| **Metadata (schema, PK, data type, upstream/downstream)** | Yes | Registry: schema (columns, types), optional `primary_key`. Upstream = pipeline `inputs`; downstream = which pipelines list this dataset as input (inverse lookup). | — |
| **Naming convention** | Yes | Enforce via convention (e.g. `raw_*`, `curated_*`, `stg_*`) and a small validator (CI or at run time) that rejects invalid names. | — |
| **Macros** | Partial | **dbt:** macros (Jinja) built-in. **Custom-only flow:** no macros unless you add a templating step (e.g. Jinja for SQL). | **Flag:** Custom engine needs macro/template layer; dbt hybrid covers it. |
| **Observability** | Yes | Run log (run_id, status, timestamps, failed checks), list runs, show run details. Optional: export to metrics later. | — |
| **Test cases of the query** | Partial | **Data quality tests:** validation engine (null, uniqueness, row count, accepted values) = tests on output. **Query unit tests** (e.g. fixture input → run query → assert output): not in base design. | **Flag:** Add optional “query test” config: input fixture + expected output or snapshot; run in CI or on demand. |

**Summary of flags**

- **Freshness SLA:** Add config (e.g. `max_age_hours`) and a freshness check step.
- **Macros (custom engine):** Add Jinja (or similar) templating for SQL if not using dbt.
- **Query unit tests:** Add fixture-based test runner if you need automated SQL correctness tests beyond DQ.

All other items are handled by the flow (registry, pipeline config, run log, optional doc generator and dependency view script).

### 7.6 Summary

- **No red flags for the minimal scope:** Everything in the code exercise (read 2–3 raw files, configurable transform, DQ checks, curated output, run log) can be implemented locally with Python + DuckDB/pandas + YAML + local files.
- **Red flags only for:** cloud, Airflow, Kubernetes, external DB, streaming, auth/RBAC — we don’t implement those; we only document or design for them.
- **Partial:** Scheduling (CLI + cron), observability (run log + simple CLI), and “production” behavior are implemented only as far as the local exercise needs; full production versions are doc-only or future work.

---

## 8. Milestones and Implementation Sequencing (Phases)

### Phase 1 — Minimal Local Framework (Code Exercise)

- **M1:** Project layout, config schema (registry + pipeline YAML), and CLI entrypoint.
- **M2:** Read 2–3 raw input files (CSV/Parquet), configurable transform (e.g. one SQL or one Python transform).
- **M3:** Validation engine: null, uniqueness, row count, accepted values; severity; run and record results.
- **M4:** Write curated output (Parquet/CSV) and run log (status, run_id, validation summary).
- **M5:** Document how to add a new pipeline and run it locally.

### Phase 2 — Adoption and Guardrails

- **M6:** Schema consistency checks (declare output schema, validate after transform).
- **M7:** Shared validation rule sets and pipeline templates.
- **M8:** Basic “list runs” and “show run log” (CLI or simple script).

### Phase 3 — Production Readiness

- **M9:** Run against cloud storage (e.g. S3 paths in registry) and optional Spark path for large data.
- **M10:** Integrate with scheduler (cron or Airflow); secrets and config from env/secret manager.
- **M11:** Observability: structured logs, metrics, and optional UI for run history.

---

## 9. Minimal Local Implementation (Code Exercise) — Approach

### Directory Layout

```
quince_demo/
├── config/
│   ├── registry.yaml          # dataset name -> path, schema
│   └── pipelines/
│       └── example_pipeline.yaml
├── data/
│   ├── raw/                    # 2–3 input files
│   └── curated/                # output
├── src/
│   ├── registry.py             # load registry, resolve paths/schemas
│   ├── transform_engine.py     # run SQL (DuckDB) or Python transform
│   ├── validation_engine.py    # run DQ rules, return results
│   ├── orchestrator.py         # run pipeline: load -> transform -> validate -> publish
│   ├── run_log.py              # write run status and log
│   └── transforms/             # optional Python transforms per pipeline
├── runs/                       # run logs (JSON or CSV)
├── run.py                      # CLI: python run.py <pipeline_name>
└── requirements.txt
```

### Config Shape (Conceptual)

**registry.yaml:**  
Datasets with `name`, `path`, optional `schema` (columns + types).

**pipeline YAML:**  
- `name`, `inputs` (list of dataset names), `transform` (type + query or module/function), `output` (dataset name), `validation` (list of rules: type, params, severity).

### Idempotency

Each run writes output to a **new file** keyed by `run_id` (e.g. `data/curated/<output_name>/<run_id>.parquet`). No overwrite; re-running the same pipeline creates a new run and new file.

### Execution Flow (One Run)

1. Parse CLI: `run.py example_pipeline`.
2. Load `config/pipelines/example_pipeline.yaml` and `config/registry.yaml`.
3. Resolve input paths from registry; read 2–3 raw files into DataFrames (or DuckDB tables).
4. Run transform (DuckDB SQL or Python). Result = one DataFrame.
5. Run validation engine on that DataFrame. Collect pass/fail per rule.
6. If any critical rule failed: write run log with status=failed, do not write curated output.
7. If all critical passed: write DataFrame to `data/curated/<output_name>/<run_id>.parquet` (new file per run; never overwrite). Write run log with status=success and validation summary.
8. Print run_id and status to stdout.

### Example Validation Rules (Implemented)

- **null_validation:** For given columns, fail if any nulls (critical or warning).
- **uniqueness_check:** For given column(s), fail if duplicates exist.
- **row_count_threshold:** Fail if row count &lt; min or &gt; max.
- **accepted_values:** For a column, fail if any value not in allowed set (or not matching regex).

### Tech Stack (Local)

- **Language:** Python 3.
- **Data:** pandas for in-memory; DuckDB for SQL transforms (optional, or pure pandas).
- **Files:** CSV and/or Parquet for raw and curated.
- **Config:** YAML (PyYAML). No AWS, Airflow, or K8s.

This gives a minimal but complete self-serve ETL: register datasets, define one transform over 2–3 inputs, configure DQ checks, and publish with a clear run log—all on a laptop, with a documented path to production.
