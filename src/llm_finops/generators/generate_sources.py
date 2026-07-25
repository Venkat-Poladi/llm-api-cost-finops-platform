from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "generated"


def as_date(value: Any) -> date:
    """Convert YAML or CSV date values to date objects."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def bool_text(value: Any) -> bool:
    """Convert common textual boolean values to bool."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into dictionaries."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def date_range(start: date, end: date) -> Iterable[date]:
    """Yield every date from start through end, inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    next_month = (value.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def months_between(start: date, current: date) -> int:
    return (current.year - start.year) * 12 + current.month - start.month


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_writer(path: Path, fieldnames: list[str]) -> tuple[Any, csv.DictWriter]:
    handle = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    return handle, writer


@dataclass(frozen=True)
class Rate:
    provider: str
    usage_type: str
    model_snapshot: str
    normalized_processing_tier: str
    is_batch: bool
    context_window_tier: str
    effective_start: date
    effective_end: date
    input_rate: float
    cached_input_rate: float | None
    cache_write_5m_rate: float | None
    cache_write_1h_rate: float | None
    output_rate: float
    contracted_discount: float


@dataclass
class ConfigBundle:
    design: dict[str, Any]
    workloads: list[dict[str, str]]
    known_events: list[dict[str, str]]
    divergences: list[dict[str, str]]
    attributions: list[dict[str, str]]
    experiments: list[dict[str, str]]
    decisions: list[dict[str, str]]
    model_map: list[dict[str, str]]
    rates: list[Rate]
    service_tier_map: dict[tuple[str, str], tuple[str, bool]]

    @classmethod
    def load(cls, config_dir: Path) -> "ConfigBundle":
        design = yaml.safe_load(
            (config_dir / "synthetic_design.yaml").read_text(encoding="utf-8")
        )
        service_config = yaml.safe_load(
            (config_dir / "service_tier_map.yaml").read_text(encoding="utf-8")
        )
        service_tier_map: dict[tuple[str, str], tuple[str, bool]] = {}
        for row in service_config["normalization"]:
            if row["used_in_v1"]:
                batch_rule = str(row["is_batch_rule"]).lower()
                mapped_batch = batch_rule == "true"
                service_tier_map[(row["provider"], row["provider_service_tier"])] = (
                    row["normalized_processing_tier"],
                    mapped_batch,
                )

        rates: list[Rate] = []
        for row in read_csv(config_dir / "model_rates.csv"):
            rates.append(
                Rate(
                    provider=row["provider"],
                    usage_type=row["usage_type"],
                    model_snapshot=row["model_snapshot"],
                    normalized_processing_tier=row["normalized_processing_tier"],
                    is_batch=bool_text(row["is_batch"]),
                    context_window_tier=row["context_window_tier"],
                    effective_start=as_date(row["effective_start"]),
                    effective_end=as_date(row["effective_end"]),
                    input_rate=float(row["input_rate_per_million"] or 0),
                    cached_input_rate=(
                        float(row["cached_input_rate_per_million"])
                        if row["cached_input_rate_per_million"]
                        else None
                    ),
                    cache_write_5m_rate=(
                        float(row["cache_write_5m_rate_per_million"])
                        if row["cache_write_5m_rate_per_million"]
                        else None
                    ),
                    cache_write_1h_rate=(
                        float(row["cache_write_1h_rate_per_million"])
                        if row["cache_write_1h_rate_per_million"]
                        else None
                    ),
                    output_rate=float(row["output_rate_per_million"] or 0),
                    contracted_discount=float(row["contracted_discount"] or 0),
                )
            )

        return cls(
            design=design,
            workloads=read_csv(config_dir / "workload_population.csv"),
            known_events=read_csv(config_dir / "known_usage_events.csv"),
            divergences=read_csv(config_dir / "cost_divergence_events.csv"),
            attributions=read_csv(config_dir / "attribution_scenarios.csv"),
            experiments=read_csv(config_dir / "experiment_controls.csv"),
            decisions=read_csv(config_dir / "experiment_decisions.csv"),
            model_map=read_csv(config_dir / "model_map.csv"),
            rates=rates,
            service_tier_map=service_tier_map,
        )

    def resolve_snapshot(self, workload: dict[str, str], usage_date: date) -> str:
        matches = [
            row
            for row in self.model_map
            if row["provider"] == workload["provider"]
            and row["usage_type"] == workload["usage_type"]
            and row["provider_model_name"] == workload["provider_model_name"]
            and as_date(row["effective_start"]) <= usage_date <= as_date(row["effective_end"])
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one model map for {workload['workload_id']} on {usage_date}; "
                f"found {len(matches)}"
            )
        return matches[0]["model_snapshot"]

    def resolve_rate(self, workload: dict[str, str], usage_date: date) -> Rate:
        snapshot = self.resolve_snapshot(workload, usage_date)
        normalized_tier, mapped_batch = self.service_tier_map[
            (workload["provider"], workload["provider_service_tier"])
        ]
        configured_batch = bool_text(workload["is_batch"])
        is_batch = configured_batch or mapped_batch
        matches = [
            rate
            for rate in self.rates
            if rate.provider == workload["provider"]
            and rate.usage_type == workload["usage_type"]
            and rate.model_snapshot == snapshot
            and rate.normalized_processing_tier == normalized_tier
            and rate.is_batch == is_batch
            and rate.context_window_tier == workload["context_window_tier"]
            and rate.effective_start <= usage_date <= rate.effective_end
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one rate for {workload['workload_id']} on {usage_date}; "
                f"found {len(matches)}"
            )
        return matches[0]


class SourceGenerator:
    """Generate deterministic, independently modeled LLM FinOps sources."""

    usage_fields = [
        "usage_date",
        "provider",
        "usage_type",
        "provider_project_id",
        "api_key_id",
        "model",
        "provider_service_tier",
        "is_batch",
        "context_window_tier",
        "request_count",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cached_input_tokens",
        "uncached_input_tokens",
        "cache_read_input_tokens",
        "cache_creation_5m_tokens",
        "cache_creation_1h_tokens",
        "is_synthetic",
    ]

    cost_fields = [
        "billing_period",
        "provider",
        "provider_project_id",
        "model",
        "line_item_scope",
        "line_item_type",
        "provider_line_item_id",
        "provider_reported_cost",
        "invoice_billed_cost",
        "billing_currency",
        "credit_amount",
        "adjustment_reason",
        "invoice_issue_date",
        "is_restatement",
        "is_synthetic",
    ]

    telemetry_fields = [
        "logical_request_id",
        "provider_request_id",
        "attempt_number",
        "attempt_status",
        "is_final_attempt",
        "final_request_status",
        "retry_reason",
        "usage_date",
        "provider",
        "provider_project_id",
        "api_key_id",
        "application_name",
        "experiment_id",
        "model",
        "failure_stage",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "cached_input_tokens",
        "uncached_input_tokens",
        "cache_read_input_tokens",
        "cache_creation_5m_tokens",
        "cache_creation_1h_tokens",
        "usage_cost_estimate",
        "is_synthetic",
    ]

    attribution_fields = [
        "mapping_id",
        "provider",
        "provider_project_id",
        "api_key_id",
        "application_name",
        "department_name",
        "cost_center",
        "allocation_percentage",
        "effective_start_date",
        "effective_end_date",
        "mapping_status",
        "allocation_method",
        "allocation_confidence",
        "mapping_recorded_date",
        "is_synthetic",
    ]

    experiment_fields = [
        "experiment_id",
        "owner",
        "approver",
        "hypothesis",
        "application_name",
        "cost_center",
        "spending_limit",
        "spending_limit_period",
        "limit_currency",
        "warning_threshold",
        "hard_stop_threshold",
        "start_date",
        "planned_end_date",
        "current_status",
        "override_reason",
        "is_synthetic",
    ]

    decision_fields = [
        "experiment_decision_id",
        "experiment_id",
        "decision",
        "decision_date",
        "decided_by",
        "rationale",
        "previous_status",
        "new_status",
        "is_synthetic",
    ]

    def __init__(
        self,
        config: ConfigBundle,
        output_dir: Path,
        *,
        profile: str = "full",
    ) -> None:
        self.config = config
        self.output_dir = output_dir
        self.profile = profile
        streams = config.design["randomness"]["streams"]
        self.usage_rng = np.random.default_rng(streams["provider_usage"])
        self.cost_rng = np.random.default_rng(streams["provider_cost"])
        self.telemetry_rng = np.random.default_rng(streams["request_telemetry"])
        self.event_index = self._build_event_index()
        self._logical_request_sequence = 0
        self._provider_request_sequence = 0

    def _build_event_index(self) -> dict[tuple[str, date], list[dict[str, str]]]:
        index: dict[tuple[str, date], list[dict[str, str]]] = defaultdict(list)
        for event in self.config.known_events:
            start = as_date(event["event_date"])
            duration = int(event["duration_days"])
            for offset in range(duration):
                index[(event["workload_id"], start + timedelta(days=offset))].append(event)
        return index

    def _profile_workloads(self) -> list[dict[str, str]]:
        if self.profile == "full":
            return self.config.workloads
        return self.config.workloads[:3]

    def _profile_period(self) -> tuple[date, date]:
        if self.profile == "full":
            period = self.config.design["reporting_period"]
            return as_date(period["start_date"]), as_date(period["end_date"])
        return date(2025, 1, 1), date(2025, 1, 14)

    def _calendar_multiplier(self, workload: dict[str, str], current: date) -> float:
        profile = self.config.design["request_generation"]["calendar_profiles"][
            workload["calendar_profile"]
        ]
        return float(
            profile["weekend_multiplier"] if current.weekday() >= 5 else profile["weekday_multiplier"]
        )

    def _event_request_multiplier(self, workload_id: str, current: date) -> float:
        multiplier = 1.0
        request_events = {
            "request_spike",
            "retry_storm",
            "embedding_spike",
            "long_context_spike",
            "runaway_experiment",
        }
        for event in self.event_index.get((workload_id, current), []):
            if event["event_type"] in request_events:
                multiplier *= float(event["multiplier"])
        return multiplier

    def _cache_event_multiplier(self, workload_id: str, current: date) -> float:
        multiplier = 1.0
        for event in self.event_index.get((workload_id, current), []):
            if event["event_type"] == "cache_drop":
                multiplier *= float(event["multiplier"])
        return multiplier

    def _mean_daily_requests(self, workload: dict[str, str], current: date) -> float:
        active_start = as_date(workload["active_start"])
        growth = (1 + float(workload["monthly_growth_rate"])) ** months_between(
            active_start, current
        )
        seasonality = float(
            self.config.design["request_generation"]["monthly_seasonality"][str(current.month)]
        )
        return max(
            1.0,
            float(workload["base_daily_requests"])
            * growth
            * self._calendar_multiplier(workload, current)
            * seasonality
            * self._event_request_multiplier(workload["workload_id"], current),
        )

    @staticmethod
    def _negative_binomial(rng: np.random.Generator, mean: float, dispersion: float) -> int:
        probability = dispersion / (dispersion + mean)
        return max(1, int(rng.negative_binomial(dispersion, probability)))

    @staticmethod
    def _lognormal_total(
        rng: np.random.Generator,
        request_count: int,
        median: float,
        sigma: float,
    ) -> int:
        if request_count <= 0 or median <= 0:
            return 0
        average = float(rng.lognormal(mean=math.log(median), sigma=sigma))
        return max(0, int(round(request_count * average)))

    def _aggregate_tokens(
        self,
        workload: dict[str, str],
        current: date,
        request_count: int,
        rng: np.random.Generator,
    ) -> dict[str, int | str]:
        token_config = self.config.design["token_generation"]
        total_input = self._lognormal_total(
            rng,
            request_count,
            float(workload["median_input_tokens"]),
            float(token_config["input_sigma"]),
        )
        total_output = self._lognormal_total(
            rng,
            request_count,
            float(workload["median_output_tokens"]),
            float(token_config["output_sigma"]),
        )
        cache_multiplier = self._cache_event_multiplier(workload["workload_id"], current)
        cache_read_share = min(1.0, float(workload["cache_read_share"]) * cache_multiplier)

        if workload["usage_type"] == "embedding":
            total_output = 0

        if workload["provider"] == "openai":
            cached = int(round(total_input * cache_read_share))
            cached = min(cached, total_input)
            return {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "reasoning_tokens": "",
                "cached_input_tokens": cached,
                "uncached_input_tokens": "",
                "cache_read_input_tokens": "",
                "cache_creation_5m_tokens": "",
                "cache_creation_1h_tokens": "",
            }

        read_tokens = int(round(total_input * cache_read_share))
        write_5m = int(round(total_input * float(workload["cache_write_5m_share"])))
        write_1h = int(round(total_input * float(workload["cache_write_1h_share"])))
        uncached = max(0, total_input - read_tokens - write_5m - write_1h)
        return {
            "input_tokens": "",
            "output_tokens": total_output,
            "reasoning_tokens": "",
            "cached_input_tokens": "",
            "uncached_input_tokens": uncached,
            "cache_read_input_tokens": read_tokens,
            "cache_creation_5m_tokens": write_5m,
            "cache_creation_1h_tokens": write_1h,
        }

    def generate_usage(self) -> dict[str, Any]:
        path = self.output_dir / "raw_ai_provider_usage.csv"
        handle, writer = csv_writer(path, self.usage_fields)
        row_count = 0
        provider_counts: dict[str, int] = defaultdict(int)
        start, end = self._profile_period()
        dispersion = float(self.config.design["request_generation"]["dispersion"])

        try:
            for workload in self._profile_workloads():
                active_start = max(start, as_date(workload["active_start"]))
                active_end = min(end, as_date(workload["active_end"]))
                if active_start > active_end:
                    continue
                for current in date_range(active_start, active_end):
                    mean = self._mean_daily_requests(workload, current)
                    requests = self._negative_binomial(self.usage_rng, mean, dispersion)
                    tokens = self._aggregate_tokens(
                        workload, current, requests, self.usage_rng
                    )
                    row = {
                        "usage_date": current.isoformat(),
                        "provider": workload["provider"],
                        "usage_type": workload["usage_type"],
                        "provider_project_id": workload["provider_project_id"],
                        "api_key_id": workload["api_key_id"],
                        "model": workload["provider_model_name"],
                        "provider_service_tier": workload["provider_service_tier"],
                        "is_batch": str(bool_text(workload["is_batch"])).lower(),
                        "context_window_tier": workload["context_window_tier"],
                        "request_count": requests if workload["provider"] == "openai" else "",
                        **tokens,
                        "is_synthetic": "true",
                    }
                    writer.writerow(row)
                    row_count += 1
                    provider_counts[workload["provider"]] += 1
        finally:
            handle.close()

        return {
            "row_count": row_count,
            "provider_row_counts": dict(sorted(provider_counts.items())),
        }

    def _rate_cost(
        self,
        rate: Rate,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        uncached_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_creation_5m_tokens: int = 0,
        cache_creation_1h_tokens: int = 0,
    ) -> float:
        if rate.provider == "openai":
            uncached_openai = max(0, input_tokens - cached_input_tokens)
            input_cost = uncached_openai * rate.input_rate
            cache_cost = cached_input_tokens * (rate.cached_input_rate or rate.input_rate)
        else:
            input_cost = uncached_input_tokens * rate.input_rate
            cache_cost = (
                cache_read_input_tokens * (rate.cached_input_rate or rate.input_rate)
                + cache_creation_5m_tokens * (rate.cache_write_5m_rate or rate.input_rate)
                + cache_creation_1h_tokens * (rate.cache_write_1h_rate or rate.input_rate)
            )
        output_cost = output_tokens * rate.output_rate
        gross = (input_cost + cache_cost + output_cost) / 1_000_000
        return gross * (1 - rate.contracted_discount)

    def _single_attempt_tokens(
        self,
        workload: dict[str, str],
        current: date,
        status: str,
        failure_stage: str,
    ) -> dict[str, int]:
        rng = self.telemetry_rng
        input_tokens = max(
            1,
            int(
                round(
                    rng.lognormal(
                        mean=math.log(max(1.0, float(workload["median_input_tokens"]))),
                        sigma=float(self.config.design["token_generation"]["input_sigma"]),
                    )
                )
            ),
        )
        output_median = float(workload["median_output_tokens"])
        output_tokens = (
            0
            if output_median == 0
            else max(
                1,
                int(
                    round(
                        rng.lognormal(
                            mean=math.log(output_median),
                            sigma=float(
                                self.config.design["token_generation"]["output_sigma"]
                            ),
                        )
                    )
                ),
            )
        )

        if status != "success":
            if failure_stage == "rejected_pre_processing":
                input_tokens = 0
                output_tokens = 0
            else:
                output_tokens = int(round(output_tokens * float(rng.uniform(0.05, 0.45))))

        cache_multiplier = self._cache_event_multiplier(workload["workload_id"], current)
        cache_read_share = min(1.0, float(workload["cache_read_share"]) * cache_multiplier)

        if workload["provider"] == "openai":
            cached = min(input_tokens, int(round(input_tokens * cache_read_share)))
            reasoning = (
                min(
                    output_tokens,
                    int(round(output_tokens * float(workload["reasoning_share_of_output"]))),
                )
                if workload["provider_model_name"] == "gpt-5"
                else 0
            )
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "reasoning_tokens": reasoning,
                "cached_input_tokens": cached,
                "uncached_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_5m_tokens": 0,
                "cache_creation_1h_tokens": 0,
            }

        read_tokens = int(round(input_tokens * cache_read_share))
        write_5m = int(round(input_tokens * float(workload["cache_write_5m_share"])))
        write_1h = int(round(input_tokens * float(workload["cache_write_1h_share"])))
        uncached = max(0, input_tokens - read_tokens - write_5m - write_1h)
        return {
            "input_tokens": 0,
            "output_tokens": output_tokens,
            "reasoning_tokens": 0,
            "cached_input_tokens": 0,
            "uncached_input_tokens": uncached,
            "cache_read_input_tokens": read_tokens,
            "cache_creation_5m_tokens": write_5m,
            "cache_creation_1h_tokens": write_1h,
        }

    def _next_logical_id(self) -> str:
        self._logical_request_sequence += 1
        return f"LR-{self._logical_request_sequence:09d}"

    def _next_provider_id(self) -> str:
        self._provider_request_sequence += 1
        return f"PR-{self._provider_request_sequence:09d}"

    def generate_telemetry(self) -> dict[str, Any]:
        path = self.output_dir / "fct_ai_request_telemetry.csv"
        handle, writer = csv_writer(path, self.telemetry_fields)
        start, end = self._profile_period()
        dispersion = float(self.config.design["request_generation"]["dispersion"])
        maximum_attempts = int(
            self.config.design["telemetry_generation"]["maximum_attempts_per_logical_request"]
        )
        cancelled_share = float(
            self.config.design["telemetry_generation"][
                "cancelled_share_of_unsuccessful_attempts"
            ]
        )
        failure_stage_weights = self.config.design["telemetry_generation"][
            "failure_stages"
        ]
        stage_names = list(failure_stage_weights)
        stage_probabilities = [float(failure_stage_weights[name]) for name in stage_names]
        retry_reasons = self.config.design["telemetry_generation"]["retry_reason_values"]

        row_count = 0
        logical_count = 0
        retry_attempt_count = 0
        successful_logical_count = 0
        failed_logical_count = 0
        total_estimated_cost = 0.0

        try:
            for workload in self._profile_workloads():
                active_start = max(start, as_date(workload["active_start"]))
                active_end = min(end, as_date(workload["active_end"]))
                if active_start > active_end:
                    continue
                for current in date_range(active_start, active_end):
                    mean = self._mean_daily_requests(workload, current)
                    logical_requests = self._negative_binomial(
                        self.telemetry_rng, mean, dispersion
                    )
                    observed_requests = int(
                        self.telemetry_rng.binomial(
                            logical_requests, float(workload["telemetry_coverage_pct"])
                        )
                    )
                    rate = self.config.resolve_rate(workload, current)

                    for _ in range(observed_requests):
                        logical_id = self._next_logical_id()
                        logical_count += 1
                        final_success = bool(
                            self.telemetry_rng.random() >= float(workload["failure_rate"])
                        )
                        has_retry = bool(
                            self.telemetry_rng.random() < float(workload["retry_rate"])
                        )
                        attempts = 1
                        if has_retry:
                            attempts = min(
                                maximum_attempts,
                                2 + int(self.telemetry_rng.geometric(0.65) - 1),
                            )
                        final_status = "success" if final_success else "failed"
                        if final_success:
                            successful_logical_count += 1
                        else:
                            failed_logical_count += 1

                        for attempt_number in range(1, attempts + 1):
                            is_final = attempt_number == attempts
                            if is_final and final_success:
                                attempt_status = "success"
                                failure_stage = ""
                                retry_reason = ""
                            else:
                                attempt_status = (
                                    "cancelled"
                                    if self.telemetry_rng.random() < cancelled_share
                                    else "failed"
                                )
                                failure_stage = str(
                                    self.telemetry_rng.choice(
                                        stage_names, p=stage_probabilities
                                    )
                                )
                                retry_reason = (
                                    ""
                                    if is_final
                                    else str(self.telemetry_rng.choice(retry_reasons))
                                )

                            tokens = self._single_attempt_tokens(
                                workload, current, attempt_status, failure_stage
                            )
                            estimated_cost = self._rate_cost(
                                rate,
                                input_tokens=tokens["input_tokens"],
                                output_tokens=tokens["output_tokens"],
                                cached_input_tokens=tokens["cached_input_tokens"],
                                uncached_input_tokens=tokens["uncached_input_tokens"],
                                cache_read_input_tokens=tokens["cache_read_input_tokens"],
                                cache_creation_5m_tokens=tokens["cache_creation_5m_tokens"],
                                cache_creation_1h_tokens=tokens["cache_creation_1h_tokens"],
                            )
                            if not is_final:
                                retry_attempt_count += 1
                            total_estimated_cost += estimated_cost

                            row = {
                                "logical_request_id": logical_id,
                                "provider_request_id": self._next_provider_id(),
                                "attempt_number": attempt_number,
                                "attempt_status": attempt_status,
                                "is_final_attempt": str(is_final).lower(),
                                "final_request_status": final_status,
                                "retry_reason": retry_reason,
                                "usage_date": current.isoformat(),
                                "provider": workload["provider"],
                                "provider_project_id": workload["provider_project_id"],
                                "api_key_id": workload["api_key_id"],
                                "application_name": workload[
                                    "telemetry_application_name"
                                ],
                                "experiment_id": workload["experiment_id"],
                                "model": workload["provider_model_name"],
                                "failure_stage": failure_stage,
                                **tokens,
                                "usage_cost_estimate": f"{estimated_cost:.9f}",
                                "is_synthetic": "true",
                            }
                            writer.writerow(row)
                            row_count += 1
        finally:
            handle.close()

        return {
            "row_count": row_count,
            "logical_request_count": logical_count,
            "successful_logical_request_count": successful_logical_count,
            "failed_logical_request_count": failed_logical_count,
            "retry_attempt_count": retry_attempt_count,
            "usage_cost_estimate": round(total_estimated_cost, 6),
        }

    def _independent_monthly_cost_estimate(
        self,
        workload: dict[str, str],
        month: date,
    ) -> float:
        month_last = month_end(month)
        active_start = max(month, as_date(workload["active_start"]))
        active_end = min(month_last, as_date(workload["active_end"]))
        if active_start > active_end:
            return 0.0

        expected_requests = 0.0
        for current in date_range(active_start, active_end):
            expected_requests += self._mean_daily_requests(workload, current)
        expected_requests *= float(self.cost_rng.lognormal(mean=0.0, sigma=0.035))

        median_input = float(workload["median_input_tokens"])
        median_output = float(workload["median_output_tokens"])
        input_tokens = int(round(expected_requests * median_input))
        output_tokens = int(round(expected_requests * median_output))
        cache_read_share = float(workload["cache_read_share"])

        rate = self.config.resolve_rate(workload, max(active_start, rate_safe_date(month)))
        if workload["provider"] == "openai":
            cached = min(input_tokens, int(round(input_tokens * cache_read_share)))
            return self._rate_cost(
                rate,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached,
            )

        read_tokens = int(round(input_tokens * cache_read_share))
        write_5m = int(round(input_tokens * float(workload["cache_write_5m_share"])))
        write_1h = int(round(input_tokens * float(workload["cache_write_1h_share"])))
        uncached = max(0, input_tokens - read_tokens - write_5m - write_1h)
        return self._rate_cost(
            rate,
            input_tokens=0,
            output_tokens=output_tokens,
            uncached_input_tokens=uncached,
            cache_read_input_tokens=read_tokens,
            cache_creation_5m_tokens=write_5m,
            cache_creation_1h_tokens=write_1h,
        )

    def _explicit_usage_divergence(
        self,
        provider: str,
        project: str,
        model: str,
        billing_month: date,
    ) -> dict[str, str] | None:
        for row in self.config.divergences:
            if (
                row["line_item_type"] == "usage"
                and row["provider"] == provider
                and row["provider_project_id"] == project
                and row["model"] == model
                and as_date(row["billing_month"]) == billing_month
            ):
                return row
        return None

    def generate_cost(self) -> dict[str, Any]:
        path = self.output_dir / "raw_ai_provider_cost.csv"
        handle, writer = csv_writer(path, self.cost_fields)
        start, end = self._profile_period()
        current_month = month_start(start)
        line_sequence = 0
        row_count = 0
        usage_line_count = 0
        non_usage_line_count = 0
        reported_total = 0.0
        invoice_total = 0.0
        usage_invoice_by_project_month: dict[tuple[str, str, date], float] = defaultdict(float)

        grouped_workloads: dict[tuple[str, str, str, date], list[dict[str, str]]] = defaultdict(list)
        while current_month <= end:
            for workload in self._profile_workloads():
                if as_date(workload["active_start"]) <= month_end(current_month) and as_date(
                    workload["active_end"]
                ) >= current_month:
                    key = (
                        workload["provider"],
                        workload["provider_project_id"],
                        workload["provider_model_name"],
                        current_month,
                    )
                    grouped_workloads[key].append(workload)
            current_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)

        try:
            for (provider, project, model, billing_month), workloads in sorted(
                grouped_workloads.items()
            ):
                independent_estimate = sum(
                    self._independent_monthly_cost_estimate(workload, billing_month)
                    for workload in workloads
                )
                if independent_estimate <= 0:
                    continue

                reported_rules = self.config.design["cost_generation"][
                    "provider_reported_cost"
                ]
                random_pct = float(
                    self.cost_rng.uniform(*reported_rules["usage_line_rounding_pct_range"])
                )
                reason = "ROUTINE_ROUNDING"
                explicit = self._explicit_usage_divergence(
                    provider, project, model, billing_month
                )
                if explicit is not None:
                    explicit_pct = float(explicit["amount_value"])
                    if explicit["amount_rule"].endswith("decrease"):
                        random_pct -= explicit_pct
                    else:
                        random_pct += explicit_pct
                    reason = explicit["variance_reason_code"]
                else:
                    divergence_draw = float(self.cost_rng.random())
                    late_probability = float(
                        reported_rules["late_usage_month_probability"]
                    )
                    cutoff_probability = float(
                        reported_rules["invoice_cutoff_month_probability"]
                    )
                    if divergence_draw < late_probability:
                        random_pct += float(
                            self.cost_rng.uniform(*reported_rules["late_usage_pct_range"])
                        )
                        reason = "LATE_USAGE"
                    elif divergence_draw < late_probability + cutoff_probability:
                        random_pct -= float(
                            self.cost_rng.uniform(*reported_rules["invoice_cutoff_pct_range"])
                        )
                        reason = "INVOICE_CUTOFF"

                reported = independent_estimate * (1 + random_pct)
                invoice_adjustment = float(
                    self.cost_rng.uniform(
                        *self.config.design["cost_generation"]["invoice_billed_cost"][
                            "usage_invoice_adjustment_pct_range"
                        ]
                    )
                )
                invoiced = reported * (1 + invoice_adjustment)
                line_sequence += 1
                row = {
                    "billing_period": billing_month.isoformat(),
                    "provider": provider,
                    "provider_project_id": project,
                    "model": model,
                    "line_item_scope": "model",
                    "line_item_type": "usage",
                    "provider_line_item_id": f"COST-{line_sequence:06d}",
                    "provider_reported_cost": f"{reported:.6f}",
                    "invoice_billed_cost": f"{invoiced:.6f}",
                    "billing_currency": "USD",
                    "credit_amount": "0.000000",
                    "adjustment_reason": reason,
                    "invoice_issue_date": (
                        month_end(billing_month) + timedelta(days=10)
                    ).isoformat(),
                    "is_restatement": "false",
                    "is_synthetic": "true",
                }
                writer.writerow(row)
                row_count += 1
                usage_line_count += 1
                reported_total += reported
                invoice_total += invoiced
                usage_invoice_by_project_month[(provider, project, billing_month)] += invoiced

            if self.profile == "full":
                for event in self.config.divergences:
                    if event["line_item_type"] == "usage":
                        continue
                    billing_month = as_date(event["billing_month"])
                    amount_rule = event["amount_rule"]
                    if amount_rule == "fixed_usd":
                        billed_amount = float(event["amount_value"])
                    elif amount_rule == "invoice_usage_pct":
                        base = usage_invoice_by_project_month[
                            (
                                event["provider"],
                                event["provider_project_id"],
                                billing_month,
                            )
                        ]
                        billed_amount = base * float(event["amount_value"])
                    else:
                        raise ValueError(f"Unsupported amount rule: {amount_rule}")

                    line_sequence += 1
                    credit_amount = (
                        billed_amount if event["line_item_type"] == "credit" else 0.0
                    )
                    row = {
                        "billing_period": billing_month.isoformat(),
                        "provider": event["provider"],
                        "provider_project_id": event["provider_project_id"],
                        "model": event["model"],
                        "line_item_scope": event["line_item_scope"],
                        "line_item_type": event["line_item_type"],
                        "provider_line_item_id": f"COST-{line_sequence:06d}",
                        "provider_reported_cost": "0.000000",
                        "invoice_billed_cost": f"{billed_amount:.6f}",
                        "billing_currency": "USD",
                        "credit_amount": f"{credit_amount:.6f}",
                        "adjustment_reason": event["variance_reason_code"],
                        "invoice_issue_date": (
                            month_end(billing_month) + timedelta(days=10)
                        ).isoformat(),
                        "is_restatement": event["is_restatement"],
                        "is_synthetic": "true",
                    }
                    writer.writerow(row)
                    row_count += 1
                    non_usage_line_count += 1
                    invoice_total += billed_amount
        finally:
            handle.close()

        return {
            "row_count": row_count,
            "usage_line_count": usage_line_count,
            "non_usage_line_count": non_usage_line_count,
            "provider_reported_cost": round(reported_total, 6),
            "invoice_billed_cost": round(invoice_total, 6),
        }

    def _copy_dimension_csv(
        self,
        filename: str,
        rows: list[dict[str, str]],
        fields: list[str],
    ) -> dict[str, Any]:
        path = self.output_dir / filename
        handle, writer = csv_writer(path, fields)
        try:
            for source in rows:
                row = {field: source.get(field, "") for field in fields}
                row["is_synthetic"] = "true"
                writer.writerow(row)
        finally:
            handle.close()
        return {"row_count": len(rows)}

    def generate_all(self, *, overwrite: bool = False) -> dict[str, Any]:
        if self.output_dir.exists() and overwrite:
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        existing_files = list(self.output_dir.glob("*"))
        if existing_files and not overwrite:
            raise FileExistsError(
                f"Output directory is not empty: {self.output_dir}. Use --overwrite."
            )

        results = {
            "raw_ai_provider_usage.csv": self.generate_usage(),
            "raw_ai_provider_cost.csv": self.generate_cost(),
            "fct_ai_request_telemetry.csv": self.generate_telemetry(),
            "bridge_ai_usage_attribution.csv": self._copy_dimension_csv(
                "bridge_ai_usage_attribution.csv",
                self.config.attributions,
                self.attribution_fields,
            ),
            "dim_ai_experiment_control.csv": self._copy_dimension_csv(
                "dim_ai_experiment_control.csv",
                self.config.experiments,
                self.experiment_fields,
            ),
            "fct_ai_experiment_decision.csv": self._copy_dimension_csv(
                "fct_ai_experiment_decision.csv",
                self.config.decisions,
                self.decision_fields,
            ),
        }

        manifest = {
            "generator_version": "1.0.0",
            "profile": self.profile,
            "reporting_period": {
                "start_date": self._profile_period()[0].isoformat(),
                "end_date": self._profile_period()[1].isoformat(),
            },
            "master_seed": self.config.design["randomness"]["master_seed"],
            "source_streams": self.config.design["randomness"]["streams"],
            "files": {},
        }
        for filename, statistics in results.items():
            path = self.output_dir / filename
            manifest["files"][filename] = {
                **statistics,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }

        manifest_path = self.output_dir / "generation_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest


def rate_safe_date(month: date) -> date:
    """Use a date inside the month for effective-dated rate resolution."""
    return month.replace(day=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic LLM FinOps sources.")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="Directory containing the locked project configuration.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where generated source files are written.",
    )
    parser.add_argument(
        "--profile",
        choices=("full", "test"),
        default="full",
        help="Use full portfolio data or a small deterministic test profile.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing generated files.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = ConfigBundle.load(args.config_dir)
    generator = SourceGenerator(config, args.output_dir, profile=args.profile)
    manifest = generator.generate_all(overwrite=args.overwrite)

    print("SOURCE GENERATION PASSED")
    for filename, details in manifest["files"].items():
        print(f"{filename}: {details['row_count']:,} rows")
    print(f"Manifest: {args.output_dir / 'generation_manifest.json'}")


if __name__ == "__main__":
    main()
