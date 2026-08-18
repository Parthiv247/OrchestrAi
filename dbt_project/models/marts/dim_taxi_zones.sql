-- marts/dim_taxi_zones.sql
-- Taxi zone dimension: pickup/dropoff location usage statistics
{{
    config(
        materialized = 'table',
        schema = 'marts'
    )
}}

WITH trips AS (
    SELECT * FROM {{ ref('stg_nyc_taxi_trips') }}
),
pickup_stats AS (
    SELECT
        pu_location_id                          AS location_id,
        COUNT(*)                                AS pickup_count,
        ROUND(AVG(total_amount)::NUMERIC, 2)    AS avg_fare_pickup,
        ROUND(SUM(total_amount)::NUMERIC, 2)    AS total_revenue_pickup
    FROM trips
    GROUP BY pu_location_id
),
dropoff_stats AS (
    SELECT
        do_location_id                          AS location_id,
        COUNT(*)                                AS dropoff_count
    FROM trips
    GROUP BY do_location_id
),
combined AS (
    SELECT
        COALESCE(p.location_id, d.location_id)  AS location_id,
        COALESCE(p.pickup_count, 0)::BIGINT      AS pickup_count,
        COALESCE(d.dropoff_count, 0)::BIGINT    AS dropoff_count,
        COALESCE(p.avg_fare_pickup, 0)          AS avg_fare,
        COALESCE(p.total_revenue_pickup, 0)     AS total_revenue
    FROM pickup_stats p
    FULL OUTER JOIN dropoff_stats d ON p.location_id = d.location_id
)
SELECT
    location_id,
    pickup_count,
    dropoff_count,
    (pickup_count + dropoff_count)::BIGINT      AS total_trips,
    avg_fare,
    total_revenue,
    CASE
        WHEN location_id IN (1, 132, 138) THEN 'Airport'
        WHEN (pickup_count + dropoff_count) > 100000 THEN 'High Traffic'
        WHEN (pickup_count + dropoff_count) > 10000  THEN 'Medium Traffic'
        ELSE 'Low Traffic'
    END                                         AS zone_tier
FROM combined
WHERE location_id IS NOT NULL
ORDER BY total_trips DESC
