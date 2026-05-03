# LLD — Detailed diagrams for interviews (Quince self-serve ETL)

Use this document for **technical interviews** and **design reviews**. It expands **`docs/LLD.md`** with **multiple Mermaid diagrams** you can paste into [Mermaid Live](https://mermaid.live), Notion, or export as PNG/SVG for slides.

**How to present (suggested order):**
1. **§1** — Process boundary (who does what).  
2. **§4** — Data plane (where data lives).  
3. **§5** — Single pipeline sequence (end-to-end).  
4. **§6** — `run.py --all` + dependency order.  
5. **§7** — Failure paths (show you think about ops).  
6. **§8** — Config + env (contract with dbt/DuckDB).

---

## How to view this LLD in a structured way

| Method | Steps |
|--------|--------|
| **Outline (recommended)** | **Cursor / VS Code** → open `docs/LLD_INTERVIEW.md` → left **Explorer** → **Outline** (headings tree). Click any section to jump. |
| **Go to Symbol in Editor** | **`Cmd+Shift+O`** (Mac) or **`Ctrl+Shift+O`** (Win/Linux) → type e.g. `5.` or `Sequence` → select heading → Enter. |
| **Markdown Preview** | **`Cmd+Shift+V`** / **`Ctrl+Shift+V`**. For **Mermaid** in preview, install extension **Markdown Preview Mermaid Support**. |
| **Jump links below** | Use the **[Table of contents](#lld-toc)** — links use stable anchors (`#lld-1` … `#lld-12`). |

---

## At-a-glance (all sections)

| § | What you’ll show | Diagram / format |
|---|------------------|------------------|
| [1](#lld-1) | Python vs dbt subprocess vs files | Flowchart |
| [2](#lld-2) | Control → orchestration → execution layers | Flowchart |
| [3](#lld-3) | `src/` module dependency graph | Flowchart |
| [4](#lld-4) | CSV → `raw` → staging → marts → curated | Flowchart |
| [5](#lld-5) | Single pipeline, numbered sequence | Sequence |
| [6](#lld-6) | `run.py --all` + topological sort | Flowchart |
| [7](#lld-7) | Failure / decision paths | Flowchart |
| [8](#lld-8) | Env vars + YAML + `profiles.yml` | Flowchart |
| [9](#lld-9) | Observability artifacts | Table |
| [10](#lld-10) | Trade-offs (Q&A) | Table |
| [11](#lld-11) | Export diagrams to slides | Steps |
| [12](#lld-12) | Related docs | Table |

---

<a id="lld-toc"></a>
## Table of contents (jump links)

1. [Process boundary & external systems](#lld-1)  
2. [Layered architecture (control vs data)](#lld-2)  
3. [Module dependency graph (detailed)](#lld-3)  
4. [Data plane — files → schemas → export](#lld-4)  
5. [Sequence — single pipeline (`run_pipeline`)](#lld-5)  
6. [`run.py --all` + topological order](#lld-6)  
7. [Failure & decision paths](#lld-7)  
8. [Configuration & environment contract](#lld-8)  
9. [Observability artifacts](#lld-9)  
10. [Trade-offs (good for interview Q&A)](#lld-10)  
11. [Export for slides](#lld-11)  
12. [Related docs](#lld-12)  

---

<a id="lld-1"></a>
## 1. Process boundary & external systems

Shows the **Python process** vs **subprocess** vs **filesystem**.

```mermaid
flowchart TB
  subgraph External["Outside Python process"]
    U[Analyst / Scheduler]
    CSV[Raw CSV files]
    FS[Curated CSV + runs.json]
  end

  subgraph Py["Python process (run.py)"]
    OR[Orchestrator]
    LD[load_raw_into_duckdb]
    EX[Export DataFrame to CSV]
    LG[append_run]
  end

  subgraph DB["DuckDB file"]
    WH[(warehouse.duckdb)]
  end

  subgraph Sub["dbt subprocess"]
    DR[dbt run]
    DT[dbt test]
  end

  U -->|CLI| OR
  OR --> LD
  OR --> DR
  OR --> DT
  OR --> EX
  OR --> LG
  LD -->|read| CSV
  LD -->|write| WH
  DR --> WH
  DT --> WH
  EX -->|read| WH
  EX -->|write| FS
  LG --> FS
```

**Talking point:** *“One orchestrator coordinates load; dbt runs as a subprocess with the same DuckDB path; we don’t embed SQL in Python.”*

---

<a id="lld-2"></a>
## 2. Layered architecture (control vs data)

```mermaid
flowchart TB
  subgraph L1["Presentation / control"]
    CLI[run.py CLI]
    CFG[YAML: registry + pipelines]
  end

  subgraph L2["Orchestration"]
    ORCH[orchestrator]
    TOPO[pipeline_run_order]
    LIN[lineage]
  end

  subgraph L3["Execution"]
    LDR[dbt_loader]
    DBTR[dbt_run]
  end

  subgraph L4["Persistence"]
    DB[(DuckDB)]
    CUR[data/curated]
    RUNL[runs/runs.json]
  end

  CLI --> ORCH
  CFG --> ORCH
  ORCH --> TOPO
  TOPO --> LIN
  ORCH --> LDR
  ORCH --> DBTR
  LDR --> DB
  DBTR --> DB
  ORCH --> CUR
  ORCH --> RUNL
```

**Talking point:** *“Config is declarative; orchestration is Python; dbt owns SQL; DuckDB is the single warehouse.”*

---

<a id="lld-3"></a>
## 3. Module dependency graph (detailed)

Maps **files under `src/`** to call direction.

```mermaid
flowchart LR
  run[run.py]

  subgraph orchestrator["orchestrator.py"]
    rp[run_pipeline]
    rap[run_all_pipelines]
  end

  subgraph pc["pipeline_config.py"]
    lpc[load_pipeline_config]
  end

  subgraph dbt_run["dbt_run.py"]
    rdp[run_dbt_pipeline]
  end

  subgraph loader["dbt_loader.py"]
    lru[load_raw_into_duckdb]
  end

  subgraph reg["registry.py"]
    rg[get_project_root]
  end

  subgraph order["pipeline_run_order.py"]
    ts[topological_sort_pipelines]
  end

  subgraph lineage["lineage.py"]
    bg[build_lineage_graph]
  end

  subgraph log["run_log.py"]
    ar[append_run]
  end

  run --> rp
  run --> rap
  run --> ts
  rap --> rp
  rp --> lpc
  rp --> rdp
  rp --> ar
  rdp --> lru
  lpc --> rg
  ts --> bg
```

**Talking point:** *“`run_all_pipelines` only calls `run_pipeline` in sorted order; lineage is only for DAG edges, not SQL execution.”*

---

<a id="lld-4"></a>
## 4. Data plane — files → schemas → export

```mermaid
flowchart LR
  subgraph Raw["Raw layer"]
    R1[orders.csv]
    R2[customers.csv]
    R3[order_items.csv]
    R4[products.csv]
  end

  subgraph Duck["DuckDB warehouse.duckdb"]
    SRAW[raw schema]
    SSTG[main_staging]
    SMART[main_marts]
  end

  subgraph Out["Publish"]
    V[run_id.csv]
    L[latest.csv]
  end

  R1 --> SRAW
  R2 --> SRAW
  R3 --> SRAW
  R4 --> SRAW
  SRAW --> SSTG
  SSTG --> SMART
  SMART --> V
  SMART --> L
```

**Talking point:** *“Loader materializes `raw.*`; dbt builds staging and marts; export reads the **final model** table for that pipeline’s `transform.model`.”*

---

<a id="lld-5"></a>
## 5. Sequence — single pipeline (`run_pipeline`)

Detailed step order (matches **`src/orchestrator.py`** + **`src/dbt_run.py`**).

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant CLI as run.py
  participant OR as orchestrator
  participant PC as pipeline_config
  participant D as dbt_run
  participant L as dbt_loader
  participant DB as DuckDB
  participant DBT as dbt CLI
  participant FS as filesystem
  participant RL as run_log

  U->>CLI: python run.py pipeline_name
  CLI->>OR: run_pipeline(name)
  OR->>OR: new run_id + timestamps
  OR->>PC: load_pipeline_config
  PC-->>OR: transform.model, output
  OR->>D: run_dbt_pipeline(model)
  D->>L: load_raw_into_duckdb
  L->>FS: read registry paths
  L->>DB: CREATE OR REPLACE raw.*
  D->>DBT: dbt run --select model+
  DBT->>DB: build models
  D->>DBT: dbt test --select model
  D->>DB: SELECT * mart/staging
  D-->>OR: DataFrame + validation_summary
  OR->>FS: write curated CSV + latest
  OR->>RL: append_run success
  OR-->>CLI: result dict
```

**Talking point:** *“Each pipeline is one `run_id`; failure is logged at any step with the same `run_id`.”*

---

<a id="lld-6"></a>
## 6. `run.py --all` + topological order

```mermaid
flowchart TB
  START([run.py --all]) --> TS[topological_sort_pipelines]
  TS --> G{lineage graph<br/>from YAML inputs}
  G --> O[Ordered list:<br/>e.g. stg_orders → orders_enriched → sales_by_brand_country]
  O --> LOOP{for each name}
  LOOP --> RP[run_pipeline name]
  RP --> OK{success?}
  OK -->|yes| LOOP
  OK -->|no| STOP[stop_on_failure: break]
  OK -->|last done| END([done])
  STOP --> END
```

**Talking point:** *“Edges come from **dataset produced_by** in lineage: if mart lists `stg_orders` as input, staging runs first. This is **orchestration order**, separate from dbt’s internal DAG.”*

---

<a id="lld-7"></a>
## 7. Failure & decision paths

```mermaid
flowchart TD
  A[run_pipeline starts] --> B{config loads?}
  B -->|no| F1[append_run failed]
  B -->|yes| C{transform.type dbt?}
  C -->|no| F1
  C -->|yes| D[run_dbt_pipeline]
  D --> E{dbt run OK?}
  E -->|no| F2[append_run + validation_summary]
  E -->|yes| G{dbt tests pass?}
  G -->|no| F2
  G -->|yes| H{export DataFrame OK?}
  H -->|no| F2
  H -->|yes| I[append_run success]
```

**Talking point:** *“We always try to persist failure to `runs.json` with `validation_summary` from dbt when available.”*

---

<a id="lld-8"></a>
## 8. Configuration & environment contract

```mermaid
flowchart LR
  subgraph Env["Environment"]
    Q[QUINCE_DUCKDB_PATH]
    P[DBT_PROFILES_DIR]
  end

  subgraph Files["Repo files"]
    RY[registry.yaml]
    PY[pipelines/*.yaml]
    PR[profiles.yml]
    DP[dbt_project/]
  end

  subgraph Runtime["Runtime"]
    LDR[loader]
    DBT[dbt subprocess]
    ORC[orchestrator reads YAML]
  end

  RY --> LDR
  PY --> ORC
  Q --> LDR
  Q --> DBT
  P --> DBT
  PR --> DBT
  DP --> DBT
```

**Talking point:** *“`QUINCE_DUCKDB_PATH` pins the same file for Python and dbt; `DBT_PROFILES_DIR` points at the folder containing `profiles.yml`.”*

---

<a id="lld-9"></a>
## 9. Observability artifacts

| Artifact | Produced by | Purpose |
|----------|-------------|---------|
| `runs/runs.json` | `run_log.append_run` | Audit: status, duration, validation |
| `dbt_project/target/run_results.json` | dbt | Parsed into `validation_summary` |
| `data/curated/.../<run_id>.csv` | pandas `to_csv` | Immutable run output |
| `data/curated/.../latest.csv` | same | Consumer “current” pointer |

---

<a id="lld-10"></a>
## 10. Trade-offs (good for interview Q&A)

| Topic | Choice | Why |
|-------|--------|-----|
| **Hybrid ETL** | Python + dbt | Self-serve YAML pipelines + tested SQL; avoid duplicating transform logic in Python |
| **Single DuckDB file** | Simplicity | Demo/local; production might separate raw vs serve or use warehouse |
| **`dbt run --select model+`** | Pulls upstream | One CLI call per pipeline; may rebuild shared nodes across pipelines |
| **CSV publish** | Portability | Easy handoff; Parquet/Delta for scale later |

---

<a id="lld-11"></a>
## 11. Export for slides

1. Open [mermaid.live](https://mermaid.live).  
2. Paste a diagram block.  
3. **Actions → PNG/SVG**.  
4. Or use **draw.io** → Arrange → Insert → Advanced → **Mermaid** (if available).

---

<a id="lld-12"></a>
## 12. Related docs

| Doc | Use |
|-----|-----|
| **`docs/LLD.md`** | Full LLD text: interfaces, JSON contracts |
| **`docs/HLD_LLD.md`** | HLD + overview |
| **`docs/HLD_DRAWIO_BLUEPRINT.md`** | draw.io HLD layout |

---

*Quince demo — hybrid self-serve ETL (Python orchestration + dbt-duckdb).*
