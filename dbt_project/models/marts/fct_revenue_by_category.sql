-- fct_revenue_by_category
-- Aggregates order revenue broken down by product category and month.
-- Used by the AI Analyst for revenue trend analysis and the Cost Optimizer demo.

WITH order_items_enriched AS (
    SELECT
        oi.order_id,
        oi.product_id,
        oi.quantity,
        oi.unit_price,
        oi.quantity * oi.unit_price                      AS line_revenue,
        p.category,
        DATE_TRUNC('month', o.created_at)::DATE          AS revenue_month
    FROM order_items oi
    JOIN products p  ON oi.product_id  = p.id
    JOIN orders   o  ON oi.order_id    = o.id
    WHERE o.status IN ('completed', 'shipped')
),

monthly_category AS (
    SELECT
        revenue_month,
        category,
        COUNT(DISTINCT order_id)                          AS order_count,
        SUM(quantity)                                     AS units_sold,
        ROUND(SUM(line_revenue)::NUMERIC, 2)              AS total_revenue,
        ROUND(AVG(line_revenue)::NUMERIC, 2)              AS avg_line_revenue,
        ROUND(SUM(line_revenue) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value
    FROM order_items_enriched
    GROUP BY revenue_month, category
)

SELECT
    revenue_month,
    category,
    order_count,
    units_sold,
    total_revenue,
    avg_line_revenue,
    avg_order_value,
    ROUND(
        100.0 * total_revenue
        / NULLIF(SUM(total_revenue) OVER (PARTITION BY revenue_month), 0),
        2
    )                                                     AS revenue_share_pct
FROM monthly_category
ORDER BY revenue_month DESC, total_revenue DESC
