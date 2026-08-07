from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from llm_finops.foundation import validate_foundation, write_foundation_evidence


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def read_csv(name: str) -> list[dict[str, str]]:
    with (CONFIG / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_m21_foundation_validator_passes() -> None:
    summary = validate_foundation(ROOT)
    assert summary["status"] == "PASS"
    assert summary["provider_channel_count"] == 5
    assert summary["production_workload_count"] == 8
    assert summary["experiment_count"] == 4
    assert summary["department_count"] == 4
    assert summary["team_count"] == 6


def test_every_workload_has_ownership_and_budget_owner() -> None:
    for row in read_csv("v2_workload_inventory.csv"):
        assert row["business_owner"]
        assert row["technical_owner"]
        assert row["budget_owner"]
        assert row["department"]
        assert row["team"]
        assert row["cost_center"]
        assert row["budget_status"] == "PENDING_M22"
        assert row["annual_budget_usd"] == ""


def test_every_workload_has_one_approved_effective_route() -> None:
    workloads = read_csv("v2_workload_inventory.csv")
    routes = read_csv("v2_approved_routes.csv")
    route_by_id = {row["approved_route_id"]: row for row in routes}

    assert len(route_by_id) == len(routes) == len(workloads)
    for workload in workloads:
        route = route_by_id[workload["approved_route_id"]]
        assert route["workload_id"] == workload["workload_id"]
        assert route["provider_channel_id"] == workload["provider_channel_id"]
        assert route["approved_model_key"]
        assert route["approval_status"].startswith("APPROVED")


def test_every_workload_has_quality_latency_and_reliability_thresholds() -> None:
    thresholds = read_csv("v2_workload_thresholds.csv")
    assert len(thresholds) == 12
    assert len({row["workload_id"] for row in thresholds}) == 12

    for row in thresholds:
        assert 0 < float(row["minimum_quality_score"]) <= 1
        assert int(row["maximum_latency_ms"]) > 0
        assert 0 < float(row["minimum_success_rate"]) <= 1
        assert 0 <= float(row["maximum_error_rate"]) < 1
        assert 0 <= float(row["maximum_retry_rate"]) < 1


def test_provider_contract_retains_channel_extensions() -> None:
    contract = yaml.safe_load(
        (CONFIG / "v2_provider_contract.yaml").read_text(encoding="utf-8")
    )
    channels = {
        row["provider_channel_id"] for row in read_csv("v2_provider_channels.csv")
    }

    assert contract["contract_version"] == "2.0.0"
    assert set(contract["provider_extensions"]) == channels
    assert "provider_reported_cost" in contract["common_financial_fields"]
    assert "invoice_billed_cost" in contract["common_financial_fields"]
    assert "Provider-specific attributes must remain available" in contract["retention_rule"]


def test_rate_card_contract_is_effective_dated() -> None:
    contract = yaml.safe_load(
        (CONFIG / "v2_rate_card_contract.yaml").read_text(encoding="utf-8")
    )
    assert contract["rate_card_version"] == "2.0.0"
    assert contract["reporting_currency"] == "USD"
    assert "effective_start" in contract["rate_key"]
    assert "effective_end" in contract["rate_key"]
    assert len(contract["controls"]) >= 6


def test_risk_control_matrix_has_required_tiers_and_actions() -> None:
    controls = read_csv("v2_risk_control_matrix.csv")
    actions = {
        "TIER_1": "BLOCK_RELEASE",
        "TIER_2": "BLOCK_DEPLOYMENT_PENDING_REVIEW",
        "TIER_3": "DOCUMENT_EXCEPTION",
    }
    counts = {tier: 0 for tier in actions}

    for row in controls:
        counts[row["tier"]] += 1
        assert row["failure_action"] == actions[row["tier"]]
        assert row["control_owner"]

    assert counts == {"TIER_1": 9, "TIER_2": 8, "TIER_3": 3}


def test_m21_evidence_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_foundation_evidence(ROOT, first)
    write_foundation_evidence(ROOT, second)
    assert first.read_bytes() == second.read_bytes()

    summary = json.loads(first.read_text(encoding="utf-8"))
    assert summary["published_metric_change"] is False
    assert summary["budget_amount_status"] == "PENDING_M22"
    assert len(summary["config_sha256"]) == 9


def test_m21_release_document_claims_no_new_financial_metrics() -> None:
    release = (ROOT / "docs/releases/m21_enterprise_foundation.md").read_text(
        encoding="utf-8"
    )
    milestone = (ROOT / "docs/m21_enterprise_workload_provider_foundation.md").read_text(
        encoding="utf-8"
    )
    assert "Metric impact\n\nNone" in release
    assert "No published v1 financial" in milestone
    assert "APPROVED_FOR_DESIGN" in release
