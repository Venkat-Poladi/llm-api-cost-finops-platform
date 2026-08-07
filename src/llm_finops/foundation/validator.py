from __future__ import annotations

from collections import Counter
from datetime import date
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


CONFIG_FILES = (
    "v2_provider_channels.csv",
    "v2_workload_inventory.csv",
    "v2_approved_routes.csv",
    "v2_workload_thresholds.csv",
    "v2_data_governance_policies.csv",
    "v2_supporting_infrastructure_categories.csv",
    "v2_risk_control_matrix.csv",
    "v2_provider_contract.yaml",
    "v2_rate_card_contract.yaml",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return value


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_foundation(root: Path) -> dict[str, Any]:
    config = root / "config"
    channels = _read_csv(config / "v2_provider_channels.csv")
    workloads = _read_csv(config / "v2_workload_inventory.csv")
    routes = _read_csv(config / "v2_approved_routes.csv")
    thresholds = _read_csv(config / "v2_workload_thresholds.csv")
    policies = _read_csv(config / "v2_data_governance_policies.csv")
    infrastructure = _read_csv(
        config / "v2_supporting_infrastructure_categories.csv"
    )
    controls = _read_csv(config / "v2_risk_control_matrix.csv")
    provider_contract = _read_yaml(config / "v2_provider_contract.yaml")
    rate_contract = _read_yaml(config / "v2_rate_card_contract.yaml")

    channel_ids = [row["provider_channel_id"] for row in channels]
    _require(len(channels) == 5, "Exactly five provider channels are required.")
    _require(len(channel_ids) == len(set(channel_ids)), "Provider channels must be unique.")
    _require(
        set(channel_ids)
        == {
            "OPENAI_DIRECT",
            "ANTHROPIC_DIRECT",
            "AMAZON_BEDROCK",
            "VERTEX_AI_GEMINI",
            "HOSTED_OPEN_SOURCE",
        },
        "Provider-channel set does not match the Phase 2 contract.",
    )
    _require(
        all(row["provider_specific_fields_retained"] == "true" for row in channels),
        "Every channel must retain provider-specific fields.",
    )

    workload_ids = [row["workload_id"] for row in workloads]
    _require(len(workloads) == 12, "Eight production and four experiment rows are required.")
    _require(len(workload_ids) == len(set(workload_ids)), "Workload IDs must be unique.")
    classes = Counter(row["workload_class"] for row in workloads)
    _require(classes == {"PRODUCTION": 8, "EXPERIMENT": 4}, "Workload classes are invalid.")
    _require(
        len({row["department"] for row in workloads}) == 4,
        "The foundation must use exactly four departments.",
    )
    _require(
        len({row["team"] for row in workloads}) == 6,
        "The foundation must use exactly six teams.",
    )
    required_workload_values = (
        "application_name",
        "feature_name",
        "business_owner",
        "technical_owner",
        "budget_owner",
        "department",
        "team",
        "cost_center",
        "environment",
        "provider_channel_id",
        "approved_route_id",
        "deployment_method",
        "data_sensitivity",
        "production_status",
        "budget_status",
        "threshold_policy_id",
        "governance_policy_id",
        "review_date",
        "effective_start",
        "effective_end",
    )
    for row in workloads:
        _require(
            all(row[field].strip() for field in required_workload_values),
            f"{row['workload_id']} has incomplete ownership or governance metadata.",
        )
        _require(
            row["provider_channel_id"] in channel_ids,
            f"{row['workload_id']} uses an unknown provider channel.",
        )
        _require(
            _parse_date(row["effective_start"]) <= _parse_date(row["effective_end"]),
            f"{row['workload_id']} has an invalid effective window.",
        )
        _require(
            row["budget_status"] == "PENDING_M22" and not row["annual_budget_usd"],
            "M21 assigns budget owners but M22 owns approved budget amounts.",
        )
        if row["workload_class"] == "EXPERIMENT":
            _require(bool(row["experiment_id"]), "Every experiment row needs an experiment ID.")
        else:
            _require(not row["experiment_id"], "Production rows must not carry experiment IDs.")

    routes_by_id = {row["approved_route_id"]: row for row in routes}
    _require(len(routes_by_id) == len(routes) == 12, "Every workload needs one unique route.")
    allowed_route_statuses = {
        "APPROVED",
        "APPROVED_FOR_DESIGN",
        "APPROVED_EXPERIMENT",
        "APPROVED_EXPERIMENT_DESIGN",
    }
    for workload in workloads:
        route = routes_by_id.get(workload["approved_route_id"])
        _require(route is not None, f"Missing route for {workload['workload_id']}.")
        _require(route["workload_id"] == workload["workload_id"], "Route workload mismatch.")
        _require(
            route["provider_channel_id"] == workload["provider_channel_id"],
            f"Provider-channel mismatch for {workload['workload_id']}.",
        )
        _require(route["approved_model_key"].strip(), "Approved model key is required.")
        _require(route["approval_status"] in allowed_route_statuses, "Invalid route status.")
        _require(
            _parse_date(route["effective_start"]) <= _parse_date(workload["effective_start"])
            and _parse_date(route["effective_end"]) >= _parse_date(workload["effective_end"]),
            f"Route window does not cover {workload['workload_id']}.",
        )

    threshold_by_id = {row["threshold_policy_id"]: row for row in thresholds}
    _require(len(threshold_by_id) == len(thresholds) == 12, "Every workload needs one threshold.")
    for workload in workloads:
        threshold = threshold_by_id.get(workload["threshold_policy_id"])
        _require(threshold is not None, f"Missing threshold for {workload['workload_id']}.")
        _require(threshold["workload_id"] == workload["workload_id"], "Threshold mismatch.")
        quality = float(threshold["minimum_quality_score"])
        reliability = float(threshold["minimum_success_rate"])
        error_rate = float(threshold["maximum_error_rate"])
        retry_rate = float(threshold["maximum_retry_rate"])
        latency = int(threshold["maximum_latency_ms"])
        _require(0 < quality <= 1, "Quality target must be within (0, 1].")
        _require(0 < reliability <= 1, "Reliability target must be within (0, 1].")
        _require(0 <= error_rate < 1 and 0 <= retry_rate < 1, "Rates are invalid.")
        _require(latency > 0, "Latency threshold must be positive.")

    policy_by_id = {row["governance_policy_id"]: row for row in policies}
    _require(len(policy_by_id) == len(policies) == 4, "Four governance policies are required.")
    for workload in workloads:
        policy = policy_by_id.get(workload["governance_policy_id"])
        _require(policy is not None, f"Missing governance policy for {workload['workload_id']}.")
        _require(
            policy["data_sensitivity"] == workload["data_sensitivity"],
            f"Sensitivity mismatch for {workload['workload_id']}.",
        )
        if workload["environment"] == "EXPERIMENT":
            _require(
                policy["allowed_environment"] == "PRODUCTION_OR_EXPERIMENT",
                f"Experiment is not permitted by {policy['governance_policy_id']}.",
            )

    infrastructure_ids = {row["infrastructure_category_id"] for row in infrastructure}
    _require(
        infrastructure_ids
        == {
            "DIRECT_MODEL",
            "RETRIEVAL",
            "ORCHESTRATION",
            "OBSERVABILITY",
            "STORAGE",
            "NETWORK",
            "HOSTED_INFERENCE",
        },
        "Infrastructure category set is incomplete.",
    )
    _require(
        all(row["included_in_fully_loaded_cost"] == "true" for row in infrastructure),
        "Every defined component must participate in fully loaded cost.",
    )

    tier_counts = Counter(row["tier"] for row in controls)
    _require(
        tier_counts == {"TIER_1": 9, "TIER_2": 8, "TIER_3": 3},
        "Risk control tier counts are incomplete.",
    )
    expected_actions = {
        "TIER_1": "BLOCK_RELEASE",
        "TIER_2": "BLOCK_DEPLOYMENT_PENDING_REVIEW",
        "TIER_3": "DOCUMENT_EXCEPTION",
    }
    for row in controls:
        _require(
            row["failure_action"] == expected_actions[row["tier"]],
            f"{row['control_id']} has the wrong failure action.",
        )
        _require(row["control_owner"].strip(), f"{row['control_id']} has no owner.")

    _require(
        provider_contract["contract_version"] == "2.0.0",
        "Provider contract version is invalid.",
    )
    _require(provider_contract["reporting_currency"] == "USD", "Only USD is supported.")
    _require(
        set(provider_contract["provider_extensions"]) == set(channel_ids),
        "Provider extension contracts must exist for every channel.",
    )
    _require(rate_contract["rate_card_version"] == "2.0.0", "Rate contract version is invalid.")
    _require(rate_contract["reporting_currency"] == "USD", "Rate currency must be USD.")
    _require(
        "effective_start" in rate_contract["rate_key"]
        and "effective_end" in rate_contract["rate_key"],
        "Rate cards must be effective-dated.",
    )

    hashes = {name: _sha256(config / name) for name in CONFIG_FILES}
    return {
        "milestone": "M21",
        "foundation_contract_version": "2.0.0",
        "provider_channel_count": len(channels),
        "production_workload_count": classes["PRODUCTION"],
        "experiment_count": classes["EXPERIMENT"],
        "department_count": len({row["department"] for row in workloads}),
        "team_count": len({row["team"] for row in workloads}),
        "approved_route_count": len(routes),
        "threshold_policy_count": len(thresholds),
        "governance_policy_count": len(policies),
        "infrastructure_category_count": len(infrastructure),
        "risk_control_count": len(controls),
        "tier_1_control_count": tier_counts["TIER_1"],
        "tier_2_control_count": tier_counts["TIER_2"],
        "tier_3_control_count": tier_counts["TIER_3"],
        "budget_amount_status": "PENDING_M22",
        "published_metric_change": False,
        "config_sha256": hashes,
        "status": "PASS",
    }


def write_foundation_evidence(root: Path, output_path: Path) -> dict[str, Any]:
    summary = validate_foundation(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
