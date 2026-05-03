# HLD diagram — draw.io blueprint (Quince self-serve ETL)

**Reference image (replicate in draw.io):** open `docs/hld_quince_etl_reference.png` in the repo — same shapes, colors, and flow as a sample HLD. Adjust arrows if needed so **Orchestrator → Python loader** and **Orchestrator → dbt** (both trigger from `run.py`), matching `src/orchestrator.py`.

Use this document to **recreate the High Level Design** in [draw.io / diagrams.net](https://app.diagrams.net/). Copy labels exactly or adapt styling (colors are suggestions).

---

## 1. Recommended canvas

| Setting | Suggestion |
|--------|------------|
| **Orientation** | Landscape (e.g. 1600×900 or larger) |
| **Style** | **Horizontal swimlanes** = layers (top = external, bottom = persistence) **or** left-to-right data flow |
| **Grid** | On, snap to grid |

---

## 2. Swimlanes (horizontal bands)

Create **5 horizontal swimlanes** (top to bottom). Title each lane on the left:

| # | Swimlane title | Purpose |
|---|----------------|---------|
| 1 | **Actors & scheduling** | People and schedulers |
| 2 | **Control plane** | CLI, orchestration, config |
| 3 | **Transform & quality** | dbt + tests |
| 4 | **Runtime execution** | Loader + DuckDB engine |
| 5 | **Persistence & outputs** | Files, DB, artifacts |

*Alternative:* Use **vertical swimlanes** (columns): **Sources | Control | Transform | Warehouse | Publish | Observability**.

---

## 3. Shapes to place (inventory)

Place **rounded rectangles** for systems/components and **cylinders** for data stores. **Actors** use stick figures or rounded person icons.

### Lane 1 — Actors & scheduling

| ID | Shape type | Label (text inside box) | Subtitle / note (small text) |
|----|------------|---------------------------|------------------------------|
| A1 | Actor | **Data engineer / Analyst** | Runs CLI, reviews lineage |
| A2 | Actor | **Scheduler (cron / Airflow / etc.)** | Optional; invokes batch runs |
| A3 | Actor | **Data producer** | Updates CSV files in `data/raw/` |

### Lane 2 — Control plane

| ID | Shape type | Label | Subtitle |
|----|------------|-------|----------|
| C1 | Rectangle | **`run.py` CLI** | Entry: single pipeline or `--all` |
| C2 | Rectangle | **Orchestrator** | `run_pipeline`, `run_all_pipelines` |
| C3 | Rectangle | **Topological sort** | Pipeline order from YAML inputs |
| C4 | Document shape | **`config/registry.yaml`** | Raw dataset → path |
| C5 | Document shape | **`config/pipelines/*.yaml`** | Pipeline → dbt model, inputs, output |
| C6 | Rectangle | **Lineage & docs helpers** | LINEAGE.md, run history, `--docs` |

### Lane 3 — Transform & quality

| ID | Shape type | Label | Subtitle |
|----|------------|-------|----------|
| T1 | Rectangle | **dbt (duckdb adapter)** | `dbt run`, `dbt test` |
| T2 | Document | **`dbt_project/`** | models, macros, `sources.yml` |
| T3 | Rectangle | **Staging models** | e.g. `stg_orders` |
| T4 | Rectangle | **Marts** | e.g. `orders_enriched`, `sales_by_brand_country` |
| T5 | Rectangle | **Schema tests** | `schema.yml`: unique, not_null, accepted_values |

### Lane 4 — Runtime execution

| ID | Shape type | Label | Subtitle |
|----|------------|-------|----------|
| R1 | Rectangle | **Python loader** | `load_raw_into_duckdb` |
| R2 | Cylinder | **DuckDB engine** | Single process SQL |
| R3 | Rectangle | **Schemas** | `raw`, `main_staging`, `main_marts` |

### Lane 5 — Persistence & outputs

| ID | Shape type | Label | Subtitle |
|----|------------|-------|----------|
| P1 | Document stack | **Raw CSVs** | `data/raw/*.csv` |
| P2 | Cylinder | **`warehouse.duckdb`** | One file; all layers |
| P3 | Document stack | **Curated CSV** | `data/curated/<output>/<run_id>.csv` |
| P4 | Document | **`latest.csv`** | Per output folder |
| P5 | Document | **`runs/runs.json`** | Audit log |
| P6 | Cloud / browser | **dbt Docs** (optional) | Model DAG, catalog |

---

## 4. Connections (arrows)

Use **directed arrows**. Add **text labels** on arrows where noted.

### From actors

| From | To | Arrow label |
|------|-----|-------------|
| A1 | C1 | CLI commands |
| A2 | C1 | `run.py --all` (scheduled) |
| A3 | P1 | Writes / updates files |

### Control plane internal

| From | To | Arrow label |
|------|-----|-------------|
| C1 | C2 | invoke |
| C2 | C4 | read registry |
| C2 | C5 | read pipeline config |
| C2 | C3 | `--all` only |
| C3 | C2 | ordered pipeline list |
| C1 | C6 | optional: lineage, docs |

### Control → runtime & transform

| From | To | Arrow label |
|------|-----|-------------|
| C2 | R1 | trigger load first |
| C2 | T1 | subprocess: `dbt run` + `dbt test` |
| T2 | T1 | compile & execute |

### Loader & warehouse

| From | To | Arrow label |
|------|-----|-------------|
| R1 | P1 | read CSV paths |
| R1 | R2 | `CREATE OR REPLACE raw.*` |
| R1 | P2 | attaches / writes DB file |
| T1 | R2 | DDL/DML on staging/marts |

### Transform internal (logical)

| From | To | Arrow label |
|------|-----|-------------|
| T2 | T3 | staging SQL |
| T2 | T4 | marts SQL |
| T3 | T4 | `ref()` chain |
| T4 | T5 | tests |

### Outputs

| From | To | Arrow label |
|------|-----|-------------|
| C2 | P3 | export DataFrame → CSV |
| C2 | P4 | write `latest.csv` |
| C2 | P5 | append run metadata |
| T1 | P6 | manifest for docs (optional) |

### Data flow (simplified backbone — **highlight in thicker line or color**)

`P1` → `R1` → `R2` (raw) → `T1` → `R2` (staging/marts) → **export** → `P3` / `P4`

---

## 5. One-page “main” diagram (minimal set)

If you need **one** clean slide, use **only**:

1. **Data producer** → **Raw CSV**  
2. **CLI** → **Orchestrator** → **Loader** → **DuckDB**  
3. **Orchestrator** → **dbt** → **DuckDB**  
4. **Orchestrator** → **Curated CSV + runs.json**  
5. **Analyst** → **CLI**  
6. **Optional Scheduler** → **CLI**

Subtitle: *Hybrid: Python (load + orchestrate + publish) + dbt (SQL + tests). Single DuckDB file.*

---

## 6. Second diagram: pipeline dependency (orchestration)

Separate smaller diagram (title: **“Pipeline execution order (`run.py --all`)"**):

- Box: **stg_orders**  
- Box: **orders_enriched**  
- Box: **sales_by_brand_country**  

Arrows: **stg_orders → orders_enriched**, **stg_orders → sales_by_brand_country**  
Caption: *Order derived from `inputs` in `config/pipelines/*.yaml`; independent of dbt `ref()` only.*

---

## 7. Third diagram: dbt logical DAG (optional HLD companion)

Title: **“dbt transformation DAG”**

- Sources: **raw.orders**, **raw.customers**, **raw.order_items**, **raw.products**  
- Model: **stg_orders**  
- Marts: **orders_enriched**, **sales_by_brand_country**  

Arrows: as in project `ref()` / `source()` relationships.

---

## 8. Color coding (suggestions for draw.io)

| Color | Use for |
|-------|---------|
| **Light blue** | Control plane (CLI, orchestrator, config) |
| **Light green** | dbt / transforms |
| **Light orange** | Python loader |
| **Purple / gray** | DuckDB warehouse |
| **Yellow** | File-based sources/outputs |
| **Pink** | Human actors |

---

## 9. Legend box (bottom-right)

Add a **legend** shape:

- **Solid arrow** = control / invoke  
- **Dashed arrow** = optional (scheduler, docs)  
- **Cylinder** = database file  
- **Document** = file-based artifact  

---

## 10. Title and footer

- **Title:** `Quince Demo — High Level Design (HLD)`  
- **Footer:** `Hybrid self-serve ETL · Python + dbt + DuckDB · v1`  

---

## 11. Export

In draw.io: **File → Export as → PNG/PDF** for slides or **SVG** for crisp scaling.

---

*This blueprint matches `docs/HLD_LLD.md` and the repository layout.*
