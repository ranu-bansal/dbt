SELECT
  order_id,
  customer_id,
  CAST(order_date AS DATE) AS order_date,
  TRIM(UPPER(country))     AS country,
  TRIM(currency)           AS currency,
  LOWER(TRIM(status))       AS status,
  total_amount,
  created_at
FROM {{ source('raw', 'orders') }}
WHERE order_id IS NOT NULL AND order_date IS NOT NULL
