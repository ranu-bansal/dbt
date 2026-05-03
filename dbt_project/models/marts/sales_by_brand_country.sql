{{
  config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=['brand_id', 'country', 'order_date']
  )
}}

SELECT
  p.brand_id,
  p.brand_name,
  TRIM(UPPER(o.country))      AS country,
  CAST(o.order_date AS DATE)   AS order_date,
  COUNT(DISTINCT o.order_id)   AS total_orders,
  SUM(i.quantity)              AS total_units,
  SUM(i.subtotal)              AS total_revenue,
  SUM(i.subtotal)              AS total_revenue_tmp
FROM {{ ref('stg_orders') }} o
JOIN {{ source('raw', 'order_items') }} i ON o.order_id = i.order_id
JOIN {{ source('raw', 'products') }} p ON i.product_id = p.product_id
WHERE {{ exclude_cancelled('o') }}
{% if is_incremental() %}
  AND CAST(o.order_date AS DATE) >= (
    SELECT COALESCE(MAX(order_date), DATE '1900-01-01') FROM {{ this }}
  )
  {% endif %}
GROUP BY p.brand_id, p.brand_name, o.country, o.order_date