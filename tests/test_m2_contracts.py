from pathlib import Path

import yaml


EXPECTED_TABLES = {
    "raw_ai_provider_usage",
    "raw_ai_provider_cost",
    "fct_ai_request_telemetry",
    "bridge_ai_usage_attribution",
    "dim_ai_model_map",
    "dim_ai_model_rate",
    "dim_ai_experiment_control",
    "fct_ai_experiment_decision",
    "fct_ai_usage_daily",
    "fct_ai_cost_reconciliation",
}


def load_contracts() -> dict:
    path = Path("config/table_contracts.yaml")
    assert path.exists(), "config/table_contracts.yaml is missing"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_all_required_contracts_exist() -> None:
    contracts = load_contracts()
    assert set(contracts["tables"]) == EXPECTED_TABLES


def test_every_contract_has_a_nonempty_grain() -> None:
    contracts = load_contracts()
    for table_name, contract in contracts["tables"].items():
        assert contract["grain"], f"{table_name} has no declared grain"
        assert len(contract["grain"]) == len(set(contract["grain"])), (
            f"{table_name} repeats a grain column"
        )


def test_daily_and_monthly_facts_have_different_grains() -> None:
    contracts = load_contracts()["tables"]
    daily_grain = set(contracts["fct_ai_usage_daily"]["grain"])
    monthly_grain = set(contracts["fct_ai_cost_reconciliation"]["grain"])

    assert "usage_date" in daily_grain
    assert "billing_month" in monthly_grain
    assert "provider_line_item_id" not in daily_grain
    assert "api_key_id" not in monthly_grain


def test_rate_card_grain_is_not_double_encoded() -> None:
    rate_grain = set(load_contracts()["tables"]["dim_ai_model_rate"]["grain"])

    assert "normalized_processing_tier" in rate_grain
    assert "is_batch" in rate_grain
    assert "context_window_tier" in rate_grain
    assert "billable_unit" not in rate_grain
    assert "provider_service_tier" not in rate_grain


def test_contract_currency_is_usd() -> None:
    assert load_contracts()["currency"] == "USD"
