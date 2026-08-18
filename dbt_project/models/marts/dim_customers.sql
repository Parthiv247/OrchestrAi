-- marts/dim_customers.sql
-- Customer dimension with lifetime value metrics and segmentation
{{
    config(
        materialized = 'table',
        schema = 'marts'
    )
}}

WITH orders AS (
    SELECT * FROM {{ ref('stg_ecommerce_orders') }}
),
agg AS (
    SELECT
        customer_id,
        COUNT(*)                                            AS total_orders,
        ROUND(SUM(total_amount)::NUMERIC, 2)                AS total_revenue,
        ROUND(AVG(total_amount)::NUMERIC, 2)                AS avg_order_value,
        MIN(ordered_at)                                     AS first_order_at,
        MAX(ordered_at)                                     AS last_order_at,
        MODE() WITHIN GROUP (ORDER BY category)             AS favorite_category,
        MODE() WITHIN GROUP (ORDER BY city)                 AS preferred_city,
        COUNT(CASE WHEN is_completed THEN 1 END)            AS completed_orders,
        COUNT(CASE WHEN status = 'cancelled' THEN 1 END)    AS cancelled_orders
    FROM orders
    GROUP BY customer_id
)
SELECT
    customer_id,
    total_orders,
    total_revenue,
    avg_order_value,
    first_order_at,
    last_order_at,
    favorite_category,
    preferred_city,
    completed_orders,
    cancelled_orders,
    ROUND(
        completed_orders::NUMERIC / NULLIF(total_orders, 0) * 100, 1
    )                                                       AS completion_rate_pct,
    CASE
        WHEN total_revenue > 1000 THEN 'VIP'
        WHEN total_revenue > 300  THEN 'Regular'
        ELSE 'Occasional'
    END                                                     AS customer_segment
FROM agg
