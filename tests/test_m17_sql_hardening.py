from pathlib import Path


SEMANTIC_DIR = Path("sql/06_semantic")


def test_financial_fact_uses_pre_normalized_aggregation() -> None:
    sql = (
        SEMANTIC_DIR / "06_fact_financial_monthly.sql"
    ).read_text(encoding="utf-8")

    assert "WITH normalized AS (" in sql
    assert "aggregated AS (" in sql
    assert "FROM aggregated;" in sql
    assert "GROUP BY\n  date_key," not in sql
    assert "GROUP BY\n    date_key," not in sql


def test_financial_id_includes_allocation_confidence() -> None:
    sql = (
        SEMANTIC_DIR / "06_fact_financial_monthly.sql"
    ).read_text(encoding="utf-8")

    hash_start = sql.index("STRUCT(\n          billing_month")
    hash_end = sql.index("        )\n      )", hash_start)
    hash_block = sql[hash_start:hash_end]

    assert "allocation_confidence" in hash_block


def test_model_keys_are_normalized_in_all_model_facts() -> None:
    for file_name in [
        "06_fact_financial_monthly.sql",
        "07_fact_usage_monthly.sql",
        "08_fact_unit_economics_monthly.sql",
        "09_fact_optimization_monthly.sql",
    ]:
        sql = (SEMANTIC_DIR / file_name).read_text(encoding="utf-8")
        assert "COALESCE(model, 'Not applicable') AS model" in sql
        assert (
            "COALESCE(model_snapshot, 'Not applicable') AS model_snapshot"
            in sql
        )
        assert (
            "COALESCE(usage_type, 'Not applicable') AS usage_type"
            in sql
        )


def test_application_dimension_normalizes_unallocated_values() -> None:
    sql = (
        SEMANTIC_DIR / "04_dim_application.sql"
    ).read_text(encoding="utf-8")

    assert "COALESCE(application_name, 'Unallocated')" in sql
    assert "COALESCE(department_name, 'Unallocated')" in sql
    assert "COALESCE(cost_center, 'UNALLOCATED')" in sql
