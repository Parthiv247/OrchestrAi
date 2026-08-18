-- marts/fct_ecommerce_summary.sql
-- Daily e-commerce revenue summary fact table
{{
    config(
        materialized = 'table',
        schema = 'marts'
    )
}}

WITH orders AS (
    SELECT * FROM {{ ref('stg_ecommerce_orders') }}
)
SELECT
    ordered_at::DATE                                                AS order_date,
    order_month_key,
    category,
    city,
    COUNT(DISTINCT order_id)                                        AS order_count,
    COUNT(DISTINCT customer_id)                                     AS unique_customers,
    SUM(quantity)                                                   AS total_units_sold,
    ROUND(SUM(total_amount)::NUMERIC, 2)                            AS total_revenue,
    ROUND(AVG(total_amount)::NUMERIC, 2)                            AS avg_order_value,
    COUNT(CASE WHEN is_completed THEN 1 END)                        AS completed_orders,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END)                AS cancelled_orders,
    ROUND(
        COUNT(CASE WHEN is_completed THEN 1 END)::NUMERIC
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                                               AS completion_rate_pct
FROM orders
GROUP BY 1, 2, 3, 4
