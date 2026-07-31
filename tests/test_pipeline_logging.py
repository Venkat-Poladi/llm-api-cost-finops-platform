from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from llm_finops.bigquery import pipeline_logging
from llm_finops.bigquery.pipeline_logging import (
    current_pipeline_run_id,
    current_pipeline_started_at,
    pipeline_run_guard,
)


DEPLOYERS = {
    "staging_deployer.py": "M7_STAGING_NORMALIZATION_PRICING",
    "reconciliation_deployer.py": "M8_MONTHLY_COST_RECONCILIATION",
    "allocation_deployer.py": "M9_DAILY_USAGE_ALLOCATION",
    "telemetry_deployer.py": "M10_TELEMETRY_RECONCILIATION",
    "token_economics_deployer.py": "M11_TOKEN_ECONOMICS",
    "application_cost_deployer.py": "M12_APPLICATION_COST_CHARGEBACK",
    "optimization_deployer.py": "M13_OPTIMIZATION_EVALUATION_GATE",
    "unit_economics_deployer.py": "M14_UNIT_ECONOMICS",
    "experiment_deployer.py": "M15_EXPERIMENT_GOVERNANCE",
    "control_deployer.py": "M16_AUTOMATED_CONTROLS_CI",
    "semantic_model_deployer.py": "M17_POWER_BI_SEMANTIC_MODEL",
}


class FakeClient:
    inserted_rows: list[tuple[str, list[dict[str, Any]]]] = []

    def __init__(self, project: str) -> None:
        self.project = project

    def insert_rows_json(
        self,
        table_id: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.inserted_rows.append((table_id, rows))
        return []


def test_pipeline_guard_logs_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "project_id: configured-project\n"
        "datasets:\n"
        "  control: configured_control\n",
        encoding="utf-8",
    )

    FakeClient.inserted_rows = []
    monkeypatch.setattr(
        pipeline_logging.bigquery,
        "Client",
        FakeClient,
    )

    @pipeline_run_guard("TEST_PIPELINE")
    def failing_deploy(
        *,
        config_path: Path,
        project_id_override: str | None = None,
    ) -> None:
        assert current_pipeline_run_id()
        assert current_pipeline_started_at()
        raise ValueError("expected failure")

    with pytest.raises(ValueError, match="expected failure"):
        failing_deploy(
            config_path=config_path,
            project_id_override="override-project",
        )

    assert len(FakeClient.inserted_rows) == 1

    table_id, rows = FakeClient.inserted_rows[0]
    assert table_id == (
        "override-project.configured_control.pipeline_run_log"
    )
    assert len(rows) == 1
    assert rows[0]["pipeline_name"] == "TEST_PIPELINE"
    assert rows[0]["status"] == "FAIL"
    assert rows[0]["loaded_table_count"] == 0
    assert rows[0]["error_message"] == "expected failure"


def test_pipeline_guard_does_not_mask_original_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "project_id: configured-project\n"
        "datasets:\n"
        "  control: configured_control\n",
        encoding="utf-8",
    )

    class BrokenClient:
        def __init__(self, project: str) -> None:
            self.project = project

        def insert_rows_json(
            self,
            table_id: str,
            rows: list[dict[str, Any]],
        ) -> list[dict[str, Any]]:
            raise RuntimeError("logging unavailable")

    monkeypatch.setattr(
        pipeline_logging.bigquery,
        "Client",
        BrokenClient,
    )

    @pipeline_run_guard("TEST_PIPELINE")
    def failing_deploy(
        *,
        config_path: Path,
        project_id_override: str | None = None,
    ) -> None:
        raise ValueError("original failure")

    with pytest.raises(ValueError, match="original failure"):
        failing_deploy(config_path=config_path)


def test_m7_to_m17_use_shared_failure_logging() -> None:
    source_root = (
        Path(__file__).parents[1]
        / "src"
        / "llm_finops"
        / "bigquery"
    )

    for filename, pipeline_name in DEPLOYERS.items():
        source = (source_root / filename).read_text(
            encoding="utf-8"
        )

        assert (
            f'@pipeline_run_guard("{pipeline_name}")'
            in source
        )
        assert (
            "pipeline_run_id = current_pipeline_run_id()"
            in source
        )
        assert (
            "started_at = current_pipeline_started_at()"
            in source
        )
        assert "import uuid" not in source
