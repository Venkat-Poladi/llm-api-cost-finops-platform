from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from llm_finops.bigquery import deployment_runner, pipeline_logging
from llm_finops.bigquery.deployment_runner import (
    SqlPipelineSpec,
    render_object_name,
    render_sql_template,
    run_sql_pipeline,
)
from llm_finops.bigquery.pipeline_logging import pipeline_run_guard


class FakeQueryJob:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def result(self) -> list[dict[str, Any]]:
        return self.rows


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, project: str) -> None:
        self.project = project
        self.queries: list[tuple[str, str]] = []
        self.created_tables: list[str] = []
        self.inserted_rows: list[tuple[str, list[dict[str, Any]]]] = []
        self.instances.append(self)

    def query(self, sql: str, location: str) -> FakeQueryJob:
        self.queries.append((sql, location))
        if "AS violation_count" in sql:
            return FakeQueryJob([{"violation_count": 0}])
        return FakeQueryJob([])

    def create_table(
        self,
        table: Any,
        exists_ok: bool = False,
    ) -> Any:
        self.created_tables.append(str(table.reference))
        return table

    def insert_rows_json(
        self,
        table_id: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.inserted_rows.append((table_id, rows))
        return []


def test_render_sql_and_object_names_are_config_driven(
    tmp_path: Path,
) -> None:
    sql_path = tmp_path / "model.sql"
    sql_path.write_text(
        "SELECT * FROM `{{PROJECT_ID}}.{{RAW_DATASET}}.source` "
        "JOIN `{{PROJECT_ID}}.{{MART_DATASET}}.target` USING (id)",
        encoding="utf-8",
    )

    datasets = {
        "raw": "configured_raw",
        "mart": "configured_mart",
    }
    rendered = render_sql_template(
        sql_path,
        "configured-project",
        datasets,
    )

    assert "configured-project.configured_raw.source" in rendered
    assert "configured-project.configured_mart.target" in rendered
    assert render_object_name(
        "{{MART_DATASET}}.mart_result",
        datasets,
    ) == "configured_mart.mart_result"


def test_shared_runner_executes_sql_controls_manifest_and_logging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path
    sql_path = project_root / "sql" / "model.sql"
    sql_path.parent.mkdir(parents=True)
    sql_path.write_text(
        "CREATE OR REPLACE TABLE "
        "`{{PROJECT_ID}}.{{MART_DATASET}}.mart_result` AS SELECT 1 AS id",
        encoding="utf-8",
    )

    config_path = project_root / "config.yaml"
    config_path.write_text(
        "project_id: configured-project\n"
        "location: US\n"
        "datasets:\n"
        "  mart: configured_mart\n"
        "  control: configured_control\n"
        "sql_files:\n"
        "  - sql/model.sql\n"
        "expected_objects:\n"
        "  - '{{MART_DATASET}}.mart_result'\n",
        encoding="utf-8",
    )

    FakeClient.instances = []
    monkeypatch.setattr(deployment_runner.bigquery, "Client", FakeClient)
    monkeypatch.setattr(pipeline_logging.bigquery, "Client", FakeClient)

    spec = SqlPipelineSpec(
        pipeline_name="TEST_SHARED_RUNNER",
        control_table="test_control_result",
        manifest_filename="test_manifest.json",
    )

    @pipeline_run_guard("TEST_SHARED_RUNNER")
    def deploy(
        *,
        project_root: Path,
        config_path: Path,
        project_id_override: str | None = None,
    ) -> dict[str, Any]:
        return run_sql_pipeline(
            project_root=project_root,
            spec=spec,
            control_query_factory=lambda project_id, datasets: {
                "no_violations": "SELECT 0 AS violation_count"
            },
        )

    manifest = deploy(
        project_root=project_root,
        config_path=config_path,
    )

    client = FakeClient.instances[0]
    assert manifest["status"] == "PASS"
    assert manifest["created_objects"] == [
        "configured_mart.mart_result"
    ]
    assert len(client.queries) == 2
    assert "configured-project.configured_mart.mart_result" in (
        client.queries[0][0]
    )

    inserted_table_ids = [table_id for table_id, _ in client.inserted_rows]
    assert (
        "configured-project.configured_control.test_control_result"
        in inserted_table_ids
    )
    assert (
        "configured-project.configured_control.pipeline_run_log"
        in inserted_table_ids
    )

    manifest_path = (
        project_root / "data" / "generated" / "test_manifest.json"
    )
    assert manifest_path.exists()
