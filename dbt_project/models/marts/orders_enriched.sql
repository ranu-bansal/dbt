SELECT
  o.order_id,
  o.customer_id,
  o.order_date,
  o.country,
  o.currency,
  o.status,
  o.total_amount,
  TRIM(c.country)              AS customer_country,
  (o.country = TRIM(c.country)) AS is_domestic
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ source('raw', 'customers') }} c ON o.customer_id = c.customer_id
WHERE o.order_id IS NOT NULL
