# Self-serve ETL platform — presentation Q&A bank

Use this when presenting **Quince-style hybrid ETL** (Python orchestration + dbt + DuckDB + YAML pipelines). Questions are grouped by type; answers are **talking points**—adapt to your audience (exec vs engineering).

---

## 1. WHAT (definitions & scope)

| Question | Answer (talking points) |
|----------|-------------------------|
| **What is “self-serve ETL” here?** | Analysts/engineers add or change pipelines through **declarative config** (`registry`, `pipelines/*.yaml`) and **dbt SQL** in-repo—without a separate ETL team wiring one-off jobs for every change. A **single CLI** (`run.py`) runs a named pipeline or all pipelines in order. |
| **What does the platform actually do end-to-end?** | **Load** registered raw files into DuckDB → **transform** with dbt models + tests → **publish** curated CSVs + **log** runs with validation summary. |
| **What is a “pipeline” in this design?** | A **named YAML** that maps to one **dbt model** (`transform.model`), an **output** folder name, and **inputs** for lineage/orchestration—not necessarily one physical DAG node in isolation. |
| **What is the role of dbt vs Python?** | **dbt** owns **SQL**, **tests**, **documentation**, and the **transformation DAG** (`ref`, `source`). **Python** owns **raw load**, **subprocess invocation**, **CSV export**, **run history**, and **pipeline-level ordering** for `--all`. |
| **What gets stored where?** | **DuckDB file**: raw + staging + marts. **Curated**: versioned CSV + `latest.csv`. **Audit**: `runs/runs.json`. **Docs**: dbt artifacts + optional lineage markdown/HTML. |

---

## 2. WHY (rationale & goals)

| Question | Answer |
|----------|--------|
| **Why hybrid (Python + dbt) instead of only dbt or only Python?** | **dbt** gives tested, reviewable SQL and a standard project layout. **Python** gives a thin **orchestration and operational** layer (load from your registry, export to business-friendly files, unified run log) without rewriting transforms in two places. |
| **Why YAML for pipelines/registry?** | **Discoverability** and **reviewability** in Git; non-SQL stakeholders can see **what** runs and **what** it depends on without reading all SQL. |
| **Why DuckDB?** | **Single-file**, **embedded** OLAP for demos and small/medium workloads—**no separate server** to operate. Good for **local → prod-like** parity when the warehouse is file-backed. |
| **Why CSV outputs if we have a database?** | **Portability** for downstream tools, **email/Slack** attachments, **QA** spot-checks, and **consumers** that don’t query SQL. |
| **Why topological sort for `--all`?** | So **orchestration order** respects **declared inputs** (e.g. staging before marts that list `stg_orders` as input)—even though dbt also has its own DAG. |

---

## 3. WHY NOT (trade-offs & rejected options)

| Question | Answer |
|----------|--------|
| **Why not Airflow-only for everything?** | Airflow is great for **scheduling** and **cross-system** ops; this stack optimizes for **git-centric**, **dbt-native** workflows with **minimal ops**. You can still **invoke** `run.py --all` from Airflow/Prefect as **one task**. |
| **Why not Spark / Flink for this use case?** | **Overkill** for warehouse-sized batch on a single node; **complexity** and **cluster ops** don’t pay off until data/team scale demands it. |
| **Why not put all transforms in Python (pandas/PySpark)?** | **Duplication** with warehouse logic, weaker **test framework** vs dbt tests, harder **lineage** and **docs** as standard as dbt’s. |
| **Why not dbt alone with no Python layer?** | You still need **something** to load raw files the way **you** want, **export** curated files, and **unify** run metadata—Python (or another tool) fills that gap. |
| **Why not one big `dbt run` every time?** | Valid pattern for **nightly full refresh**; **per-pipeline** runs support **incremental operational** use (only refresh what you need) and **clearer** ownership per output. |

---

## 4. WHAT ELSE (extensions, comparisons, “day 2”)

| Question | Answer |
|----------|--------|
| **What else would you add for production?** | **Secrets** management, **RBAC** on who can change pipelines, **backups** of DuckDB or **move to cloud warehouse**, **monitoring/alerting** (failed runs), **data contracts** with consumers, **SLAs**, **cost** tracking. |
| **What else for scale?** | **Partition** raw data, **incremental** dbt models, **Parquet** instead of CSV, **warehouse** (Snowflake/BigQuery) instead of single DuckDB file, **parallel** execution with care for **locking**. |
| **What else for governance?** | **PR reviews** on YAML + SQL, **environments** (dev/stg/prod), **dbt exposures** / **semantic layer** if needed, **PII** tagging and **masking**. |
| **How does this compare to Fivetran / ELT tools?** | Those tools excel at **SaaS connectors** and **managed load**; this pattern is **bring-your-own-files** + **full control** in Git—**different** sweet spot. |
| **What about real-time / streaming?** | This design is **batch**. Streaming would need **Kafka/Kinesis**, **CDC**, and a different **processing** layer—not a drop-in. |

---

## 5. HOW (operational & technical depth)

| Question | Answer |
|----------|--------|
| **How does a new pipeline get added?** | Register raw (if needed) → add dbt model + `schema.yml` → add `config/pipelines/<name>.yaml` → run `python run.py <name>`. |
| **How does dependency order work for `--all`?** | **Lineage** from YAML **inputs** and dataset **produced_by**; **Kahn** topological sort; **cycles** error. |
| **How does testing work?** | **dbt tests** (`unique`, `not_null`, `accepted_values`, etc.) tied to models; results flow into **`validation_summary`** and **`runs.json`**. |
| **How do you debug failures?** | **`runs.json`** + humanized **dbt** messages; **`target/run_results.json`**; **compiled SQL** under `dbt_project/target/`. |
| **How is idempotency handled?** | Each run **new `run_id`**; **`raw`** tables **replaced** from CSV; **views/tables** rebuilt by dbt; **curated** immutable per run + **`latest`** pointer. |

---

## 6. RISKS / CHALLENGES (expect “gotcha” questions)

| Question | Answer |
|----------|--------|
| **Single DuckDB file — isn’t that a bottleneck?** | Yes for **concurrent writers**; acceptable for **single-runner** batch. **Mitigation**: one writer process, or **separate** DBs/envs, or **graduate** to a server warehouse. |
| **Pipeline YAML vs dbt DAG — two sources of truth?** | **YAML** = **orchestration** + **dataset lineage**; **dbt** = **SQL dependency** graph. They must **align** on inputs (e.g. list `stg_orders` if the model `ref`s it). |
| **Running `dbt run --select model+` per pipeline — redundant work?** | **Upstream models** may **rebuild** across pipelines; acceptable for **simplicity**; **optimize** with a **single** `dbt run` for full refresh if needed. |
| **CSV in production?** | Often **intermediate**; **Parquet/Delta** or **direct warehouse** access is better at scale—**design choice** to clarify. |

---

## 7. BEHAVIORAL / OWNERSHIP (“soft” questions)

| Question | Answer |
|----------|--------|
| **Who owns the pipelines?** | Ideally **domain teams** own their YAML + SQL with **platform** standards (templates, reviews, CI). |
| **How do you prevent breaking changes?** | **CI**: `dbt test`, `dbt compile`, optional **Python tests**; **PR** review; **consumer** comms for **schema** changes. |
| **What would you say to a stakeholder who wants “no code”?** | **YAML + dbt** are still **code**—clarity is **low-code** compared to bespoke Python ETL; **true** no-code usually needs a **vendor product** with different trade-offs. |

---

## 8. Quick flash-card answers (one-liners)

- **What is it?** Git-backed, **self-serve** batch ETL: **load → dbt → test → export → log**.  
- **Why dbt?** **SQL + tests + docs** as standard artifacts.  
- **Why Python?** **Orchestration**, **raw load**, **publish**, **audit**.  
- **Why not X?** Match **answer** to **scale** and **ops maturity**—don’t over-engineer.  
- **Production gap?** **Security, scale, monitoring, multi-env**, and **warehouse** choice.  

---

*Tailor answers to your actual deployment (demo vs production roadmap).*
