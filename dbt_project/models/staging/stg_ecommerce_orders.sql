-- staging/stg_ecommerce_orders.sql
-- Cleans and standardizes raw e-commerce order records
{{
    config(
        materialized = 'view',
        schema = 'staging'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('orchestrai', 'ecommerce_orders') }}
)
SELECT
    id::BIGINT                                              AS order_key,
    order_id,
    customer_id::INTEGER                                    AS customer_id,
    product_id::INTEGER                                     AS product_id,
    TRIM(product_name)                                      AS product_name,
    TRIM(category)                                         AS category,
    ROUND(unit_price::NUMERIC, 2)                          AS unit_price,
    quantity::INTEGER                                      AS quantity,
    ROUND(total_amount::NUMERIC, 2)                        AS total_amount,
    LOWER(TRIM(status))                                    AS status,
    LOWER(TRIM(status)) IN ('delivered', 'shipped')        AS is_completed,
    TRIM(city)                                             AS city,
    TRIM(COALESCE(country, 'Unknown'))                     AS country,
    created_at                                             AS ordered_at,
    EXTRACT(YEAR FROM created_at)::INTEGER                 AS order_year,
    EXTRACT(MONTH FROM created_at)::INTEGER                AS order_month,
    EXTRACT(DOW FROM created_at)::INTEGER                  AS order_dow,
    TO_CHAR(created_at, 'YYYY-MM')                         AS order_month_key
FROM source
WHERE order_id IS NOT NULL
  AND total_amount > 0
