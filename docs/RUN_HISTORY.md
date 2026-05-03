# Pipeline run history (recent)

Last **10** runs from `runs/runs.json`. **Runtime** is end-to-end for that pipeline (load raw → dbt run/test → export CSV), not per SQL statement.

Re-generate: `python run.py --runs-write`

---

## LLD: Orchestrator flow (reference)

End-to-end steps for a single pipeline run (`python run.py <pipeline>`).
For **`--all`**, pipelines run in **topological order** from `config/pipelines/*.yaml` inputs (`pipeline_run_order`).

### Module call chain

`run.py` → `orchestrator.run_pipeline` → `dbt_run.run_dbt_pipeline` → `dbt_loader.load_raw_into_duckdb` + subprocess **dbt** → pandas export → `run_log.append_run`.

### Control flow (diagram)

```mermaid
flowchart LR
  A[run.py] --> B[Pipeline YAML]
  B --> C[load_raw_into_duckdb]
  C --> D[dbt run model+]
  D --> E[dbt test model]
  E --> F[Export CSV]
  F --> G[runs.json]
```

### Ordered steps

1. **Resolve config** — `config/pipelines/<name>.yaml` (`transform.model`, `output`).
2. **Load raw** — `registry.yaml` → `CREATE OR REPLACE raw.*` in `warehouse.duckdb`.
3. **dbt run** — `dbt run --select <model>+` (builds model + upstream refs in selection).
4. **dbt test** — `dbt test --select <model>`.
5. **Export** — `SELECT *` from `main_staging` / `main_marts` for that model → CSV.
6. **Publish** — `data/curated/<output>/<run_id>.csv` and `latest.csv`.
7. **Log** — append to `runs/runs.json` (status, duration, `validation_summary`).

Full LLD (interfaces, data contracts): **`docs/LLD.md`**. **Interview diagrams** (many figures + talking points): **`docs/LLD_INTERVIEW.md`**.

---

| Run ID | Pipeline | Status | Runtime (s) | Started (UTC) | Finished (UTC) |
|--------|----------|--------|-------------|---------------|----------------|
| `20260321_213600_73e714be` | sales_by_brand_country | success | 4.789 | 2026-03-21T21:36:00.461518+00:00 | 2026-03-21T21:36:05.250805+00:00 |
| `20260321_213509_f3bf228b` | sales_by_brand_country | failed | 2.547 | 2026-03-21T21:35:09.001716+00:00 | 2026-03-21T21:35:11.548785+00:00 |
| `20260321_212649_5c5bf0f7` | stg_orders | failed | 2.748 | 2026-03-21T21:26:49.903071+00:00 | 2026-03-21T21:26:52.650819+00:00 |
| `20260321_212520_ddac4938` | stg_orders | failed | 2.655 | 2026-03-21T21:25:20.343239+00:00 | 2026-03-21T21:25:22.998636+00:00 |
