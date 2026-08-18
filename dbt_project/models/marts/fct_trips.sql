-- marts/fct_trips.sql
-- Trip-level fact table for NYC Taxi analytics
{{
    config(
        materialized = 'table',
        schema = 'marts'
    )
}}

WITH trips AS (
    SELECT * FROM {{ ref('stg_nyc_taxi_trips') }}
)
SELECT
    trip_id,
    pickup_at::DATE                                                             AS pickup_date,
    pickup_hour,
    pickup_day_of_week,
    vendor_name,
    pu_location_id,
    do_location_id,
    passenger_count,
    trip_distance_miles,
    trip_duration_min,
    CASE
        WHEN trip_duration_min > 0
        THEN ROUND((trip_distance_miles / (trip_duration_min / 60.0))::NUMERIC, 2)
        ELSE NULL
    END                                                                         AS avg_speed_mph,
    fare_amount,
    tip_amount,
    CASE
        WHEN fare_amount > 0
        THEN ROUND((tip_amount / fare_amount * 100)::NUMERIC, 1)
        ELSE 0
    END                                                                         AS tip_pct,
    total_amount,
    payment_method,
    is_airport_trip
FROM trips
