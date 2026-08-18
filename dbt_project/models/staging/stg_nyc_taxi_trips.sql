-- staging/stg_nyc_taxi_trips.sql
-- Cleans and standardizes raw NYC Yellow Taxi trip records
{{
    config(
        materialized = 'view',
        schema = 'staging'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('orchestrai', 'nyc_taxi_trips') }}
),
cleaned AS (
    SELECT
        id::BIGINT                                                           AS trip_id,
        CASE vendor_id
            WHEN 1 THEN 'Creative Mobile'
            WHEN 2 THEN 'VeriFone'
            ELSE 'Unknown'
        END                                                                  AS vendor_name,
        pickup_datetime                                                      AS pickup_at,
        dropoff_datetime                                                     AS dropoff_at,
        EXTRACT(HOUR FROM pickup_datetime)::INTEGER                          AS pickup_hour,
        EXTRACT(DOW FROM pickup_datetime)::INTEGER                           AS pickup_day_of_week,
        ROUND(
            EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) / 60.0,
            2
        )::NUMERIC                                                           AS trip_duration_min,
        COALESCE(trip_distance, 0)::NUMERIC                                  AS trip_distance_miles,
        CASE
            WHEN passenger_count IS NULL OR passenger_count != passenger_count
              OR passenger_count < 0 OR passenger_count > 9
            THEN 1
            ELSE passenger_count::INTEGER
        END                                                                  AS passenger_count,
        pu_location_id,
        do_location_id,
        CASE payment_type
            WHEN 1 THEN 'Credit Card'
            WHEN 2 THEN 'Cash'
            WHEN 3 THEN 'No Charge'
            WHEN 4 THEN 'Dispute'
            ELSE 'Unknown'
        END                                                                  AS payment_method,
        ROUND(COALESCE(fare_amount, 0)::NUMERIC, 2)                         AS fare_amount,
        ROUND(COALESCE(tip_amount, 0)::NUMERIC, 2)                          AS tip_amount,
        ROUND(COALESCE(total_amount, 0)::NUMERIC, 2)                        AS total_amount,
        (
            pu_location_id IN (1, 132, 138)
            OR do_location_id IN (1, 132, 138)
        )                                                                    AS is_airport_trip
    FROM source
    WHERE pickup_datetime IS NOT NULL
      AND dropoff_datetime IS NOT NULL
      AND dropoff_datetime > pickup_datetime
      AND COALESCE(trip_distance, 0) >= 0
      AND COALESCE(total_amount, 0) > 0
      AND EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)) BETWEEN 60 AND 7200
)
SELECT * FROM cleaned
