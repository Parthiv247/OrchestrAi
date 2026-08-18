{% macro cents_to_dollars(column_name) %}
    ({{ column_name }} / 100.0)
{% endmacro %}

{% macro safe_divide(numerator, denominator) %}
    CASE WHEN {{ denominator }} = 0 OR {{ denominator }} IS NULL
         THEN NULL
         ELSE {{ numerator }}::FLOAT / {{ denominator }}
    END
{% endmacro %}

{% macro date_spine_cte(start_date, end_date) %}
    SELECT generate_series(
        '{{ start_date }}'::date,
        '{{ end_date }}'::date,
        '1 day'::interval
    )::date AS date_day
{% endmacro %}

{% macro not_empty_string(column_name) %}
    {{ column_name }} IS NOT NULL AND TRIM({{ column_name }}) != ''
{% endmacro %}
