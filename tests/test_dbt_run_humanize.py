"""ANSI stripping and dbt log formatting for readable runs.json messages."""
from src.dbt_run import _humanize_dbt_output


def test_strips_ansi_and_keeps_failure_block():
    raw = (
        "\x1b[0m21:16:35  1 of 3 OK created sql view model main_staging.stg_orders\n"
        "\x1b[0m21:16:35  3 of 3 ERROR creating sql incremental model main_marts.sales_by_brand_country\n"
        "\x1b[0m21:16:35  \x1b[31mFailure in model sales_by_brand_country (models/marts/sales_by_brand_country.sql)\x1b[0m\n"
        "\x1b[0m21:16:35    Runtime Error in model sales_by_brand_country\n"
        "  Parser Error: syntax error at or near \"ELECT\"\n"
    )
    out = _humanize_dbt_output(raw)
    assert "\x1b" not in out
    assert "Failure in model sales_by_brand_country" in out
    assert "Parser Error" in out
    assert "1 of 3 OK" not in out  # noise before failure block dropped
    assert "21:16:35" not in out  # timestamps stripped from lines
    assert "ERROR creating" not in out  # prefer Failure block over earlier ERROR line


def test_strips_deprecation_tail():
    raw = """21:22:55  Failure in model m (models/m.sql)
21:22:55    Runtime Error: oops
21:22:55  Done. PASS=0 WARN=0 ERROR=1 SKIP=0 NO-OP=0 TOTAL=1
21:22:55  [WARNING][DeprecationsSummary]: Deprecated functionality
Summary of encountered deprecations:
- MissingArgumentsPropertyInGenericTestDeprecation: 1 occurrence
"""
    out = _humanize_dbt_output(raw)
    assert "DeprecationsSummary" not in out
    assert "MissingArgumentsProperty" not in out
    assert "Done." not in out
    assert "Failure in model m" in out
    assert "oops" in out
