-- fct_customer_cohort
-- Cohort retention analysis: tracks what % of customers from each acquisition
-- month are still purchasing in subsequent months.
-- Demonstrates the AI Analyst's ability to run complex window-function queries.

WITH customer_first_order AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(created_at))::DATE        AS cohort_month
    FROM orders
    WHERE status IN ('completed', 'shipped')
    GROUP BY customer_id
),

customer_activity AS (
    SELECT
        o.customer_id,
        DATE_TRUNC('month', o.created_at)::DATE           AS activity_month,
        SUM(o.order_total)                                AS monthly_revenue
    FROM orders o
    WHERE o.status IN ('completed', 'shipped')
    GROUP BY o.customer_id, DATE_TRUNC('month', o.created_at)::DATE
),

cohort_data AS (
    SELECT
        cf.cohort_month,
        ca.activity_month,
        EXTRACT(MONTH FROM AGE(ca.activity_month, cf.cohort_month))::INT AS months_since_acquisition,
        COUNT(DISTINCT ca.customer_id)                    AS active_customers,
        ROUND(SUM(ca.monthly_revenue)::NUMERIC, 2)        AS cohort_revenue
    FROM customer_first_order cf
    JOIN customer_activity ca ON cf.customer_id = ca.customer_id
    GROUP BY cf.cohort_month, ca.activity_month
),

cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM customer_first_order
    GROUP BY cohort_month
)

SELECT
    cd.cohort_month,
    cd.activity_month,
    cd.months_since_acquisition,
    cs.cohort_size,
    cd.active_customers,
    ROUND(100.0 * cd.active_customers / NULLIF(cs.cohort_size, 0), 1) AS retention_pct,
    cd.cohort_revenue,
    ROUND(cd.cohort_revenue / NULLIF(cd.active_customers, 0), 2)       AS revenue_per_active_customer
FROM cohort_data cd
JOIN cohort_sizes cs ON cd.cohort_month = cs.cohort_month
ORDER BY cd.cohort_month, cd.months_since_acquisition
