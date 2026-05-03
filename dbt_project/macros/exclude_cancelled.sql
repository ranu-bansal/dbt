{% macro exclude_cancelled(alias) %}
LOWER(TRIM({{ alias }}.status)) NOT IN ('cancelled')
{% endmacro %}
