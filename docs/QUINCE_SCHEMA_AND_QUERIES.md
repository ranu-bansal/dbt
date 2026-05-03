# Quince E-Commerce: Table Structure & Example Transformations

Quince is an e-commerce company that sells luxury clothing from multiple brands in the US, UK, and Canada. This document defines a practical table structure and example SQL transformations for the self-serve ETL use case.

---

## 1. Table Structure (Database Schema)

### 1.1 Raw / Source-Like Tables (Inputs)

These represent data as it might land from orders, products, and customers (e.g. CSV/Parquet from internal systems or exports).

#### `raw_products`

| Column        | Type     | Description                          |
|---------------|----------|--------------------------------------|
| product_id    | VARCHAR  | Unique product identifier            |
| brand_id      | VARCHAR  | Brand (e.g. Quince Cashmere, etc.)   |
| brand_name    | VARCHAR  | Human-readable brand name            |
| category      | VARCHAR  | e.g. Sweaters, Pants, Outerwear      |
| product_name  | VARCHAR  | Product title                        |
| unit_price_usd| DECIMAL  | Base price in USD                    |
| currency      | VARCHAR  | USD, GBP, CAD                        |
| created_at    | TIMESTAMP| When product was added to catalog    |

#### `raw_orders`

| Column         | Type     | Description                          |
|----------------|----------|--------------------------------------|
| order_id       | VARCHAR  | Unique order identifier              |
| customer_id    | VARCHAR  | Reference to customer                |
| order_date     | DATE     | Order placement date                 |
| country        | VARCHAR  | US, UK, Canada                       |
| currency       | VARCHAR  | USD, GBP, CAD                        |
| status         | VARCHAR  | pending, shipped, delivered, cancelled |
| total_amount   | DECIMAL  | Order total in order currency        |
| created_at     | TIMESTAMP| Record created at                     |

#### `raw_order_items`

| Column      | Type    | Description                    |
|-------------|---------|--------------------------------|
| order_id    | VARCHAR | FK to order                    |
| line_item_id| VARCHAR | Unique line id                 |
| product_id  | VARCHAR | FK to product                  |
| quantity    | INT     | Units ordered                  |
| unit_price  | DECIMAL | Price at time of order         |
| subtotal    | DECIMAL | quantity * unit_price          |

#### `raw_customers`

| Column     | Type     | Description                |
|------------|----------|----------------------------|
| customer_id| VARCHAR  | Unique customer id         |
| country    | VARCHAR  | Primary country (US/UK/CA) |
| email      | VARCHAR  | Contact email              |
| first_order_date | DATE | First order date       |
| created_at | TIMESTAMP| Record created at          |

---

### 1.2 Staging / Cleaned Tables (After Light Cleansing)

Same structure as raw but with basic cleaning (trimmed strings, valid enums). Names: `stg_products`, `stg_orders`, `stg_order_items`, `stg_customers`.

---

### 1.3 Curated / Mart Tables (Outputs for Reporting & ETL)

#### `curated_orders_enriched`

One row per order with customer and country context; used for order-level reporting.

| Column           | Type     | Description                    |
|------------------|----------|--------------------------------|
| order_id         | VARCHAR  | PK                             |
| customer_id      | VARCHAR  |                                |
| order_date       | DATE     |                                |
| country          | VARCHAR  | US, UK, Canada                 |
| currency         | VARCHAR  |                                |
| status           | VARCHAR  |                                |
| total_amount     | DECIMAL  |                                |
| customer_country | VARCHAR  | From customers                 |
| is_domestic      | BOOLEAN  | order country = customer country |

#### `curated_sales_by_brand_country`

Aggregated sales by brand and country (for dashboards).

| Column        | Type    | Description              |
|---------------|---------|--------------------------|
| brand_id      | VARCHAR |                          |
| brand_name    | VARCHAR |                          |
| country       | VARCHAR | US, UK, Canada           |
| order_date    | DATE    | (or month, depending on grain) |
| total_orders  | INT     | Count of orders          |
| total_units   | INT     | Sum of quantities        |
| total_revenue | DECIMAL | Sum of subtotals (or converted to USD) |

#### `curated_product_performance`

Product-level metrics for reporting/experimentation.

| Column         | Type    | Description                |
|----------------|---------|----------------------------|
| product_id     | VARCHAR | PK                         |
| brand_id       | VARCHAR |                            |
| category       | VARCHAR |                            |
| country        | VARCHAR | US, UK, Canada             |
| units_sold     | INT     | Sum of quantity            |
| revenue        | DECIMAL | Sum of subtotal            |
| order_count    | INT     | Distinct orders            |

---

## 2. Example Transformation Queries

Below are **simple transformations** you can run in DuckDB (or any SQL engine) against the raw/staging tables. They match the kind of logic the self-serve ETL would execute (e.g. in dbt models or a single SQL step).

### 2.1 Staging: Clean and Normalize Orders

```sql
-- stg_orders: trim and standardize status and country
SELECT
  order_id,
  customer_id,
  CAST(order_date AS DATE) AS order_date,
  UPPER(TRIM(country))    AS country,
  TRIM(currency)          AS currency,
  LOWER(TRIM(status))     AS status,
  total_amount,
  created_at
FROM raw_orders
WHERE order_id IS NOT NULL
  AND order_date IS NOT NULL;
```

### 2.2 Staging: Clean Products

```sql
-- stg_products: normalize category and brand
SELECT
  product_id,
  brand_id,
  TRIM(brand_name)     AS brand_name,
  TRIM(category)       AS category,
  product_name,
  unit_price_usd,
  TRIM(currency)       AS currency,
  created_at
FROM raw_products
WHERE product_id IS NOT NULL;
```

### 2.3 Curated: Orders Enriched (Orders + Customer Country + Domestic Flag)

```sql
-- curated_orders_enriched: one row per order with customer context
SELECT
  o.order_id,
  o.customer_id,
  o.order_date,
  o.country,
  o.currency,
  o.status,
  o.total_amount,
  c.country AS customer_country,
  (o.country = c.country) AS is_domestic
FROM stg_orders o
LEFT JOIN stg_customers c ON o.customer_id = c.customer_id
WHERE o.order_id IS NOT NULL;
```

### 2.4 Curated: Sales by Brand and Country (Daily Grain)

```sql
-- curated_sales_by_brand_country: aggregate for reporting
SELECT
  p.brand_id,
  p.brand_name,
  o.country,
  o.order_date,
  COUNT(DISTINCT o.order_id)   AS total_orders,
  SUM(i.quantity)             AS total_units,
  SUM(i.subtotal)             AS total_revenue
FROM stg_orders o
JOIN stg_order_items i ON o.order_id = i.order_id
JOIN stg_products p   ON i.product_id = p.product_id
WHERE o.status NOT IN ('cancelled')
GROUP BY 1, 2, 3, 4;
```

### 2.5 Curated: Product Performance by Country

```sql
-- curated_product_performance: product-level metrics by country
SELECT
  p.product_id,
  p.brand_id,
  p.category,
  o.country,
  SUM(i.quantity)           AS units_sold,
  SUM(i.subtotal)           AS revenue,
  COUNT(DISTINCT o.order_id) AS order_count
FROM stg_orders o
JOIN stg_order_items i ON o.order_id = i.order_id
JOIN stg_products p   ON i.product_id = p.product_id
WHERE o.status NOT IN ('cancelled')
GROUP BY p.product_id, p.brand_id, p.category, o.country;
```

### 2.6 Simple KPIs: Revenue by Country (Last 30 Days)

```sql
SELECT
  country,
  SUM(total_amount) AS revenue,
  COUNT(*)          AS order_count
FROM stg_orders
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
  AND status NOT IN ('cancelled')
GROUP BY country
ORDER BY revenue DESC;
```

### 2.7 Top Brands by Units Sold (All Countries)

```sql
SELECT
  p.brand_name,
  SUM(i.quantity) AS total_units,
  SUM(i.subtotal) AS total_revenue
FROM stg_orders o
JOIN stg_order_items i ON o.order_id = i.order_id
JOIN stg_products p   ON i.product_id = p.product_id
WHERE o.status NOT IN ('cancelled')
GROUP BY p.brand_name
ORDER BY total_units DESC
LIMIT 10;
```

### 2.8 Domestic vs Cross-Country Orders (Using Enriched Table)

```sql
SELECT
  is_domestic,
  COUNT(*) AS order_count,
  SUM(total_amount) AS revenue
FROM curated_orders_enriched
WHERE status NOT IN ('cancelled')
GROUP BY is_domestic;
```

---

## 3. How This Fits the Self-Serve ETL

- **Raw tables** → Registered in the **registry** (paths to CSV/Parquet); ETL **reads** these.
- **Staging** → Produced by a first transformation step (e.g. `stg_orders.sql`, `stg_products.sql`).
- **Curated** → Produced by transformations that join staging tables (e.g. `curated_orders_enriched.sql`, `curated_sales_by_brand_country.sql`).
- **Data quality** → Run checks on staging/curated: e.g. `order_id` not null and unique, `country` in (`US`,`UK`,`Canada`), `status` in allowed set, row count thresholds.

Using this schema and these queries, you can wire one pipeline per curated dataset (e.g. “orders_enriched”, “sales_by_brand_country”) in the minimal ETL with 2–3 raw inputs (e.g. orders, order_items, products) and one configurable SQL transform.
