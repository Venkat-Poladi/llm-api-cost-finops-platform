from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar
import os
import uuid

import yaml
from google.cloud import bigquery

from llm_finops.bigquery.identifiers import validate_bigquery_identifiers


P = ParamSpec("P")
R = TypeVar("R")

_PIPELINE_RUN_ID: ContextVar[str | None] = ContextVar(
    "pipeline_run_id",
    default=None,
)
_PIPELINE_STARTED_AT: ContextVar[datetime | None] = ContextVar(
    "pipeline_started_at",
    default=None,
)
_PIPELINE_CONFIG: ContextVar[dict[str, Any] | None] = ContextVar(
    "pipeline_config",
    default=None,
)
_PIPELINE_PROJECT_ID: ContextVar[str | None] = ContextVar(
    "pipeline_project_id",
    default=None,
)
_PIPELINE_DATASETS: ContextVar[dict[str, str] | None] = ContextVar(
    "pipeline_datasets",
    default=None,
)
_PIPELINE_LOADED_TABLE_COUNT: ContextVar[int] = ContextVar(
    "pipeline_loaded_table_count",
    default=0,
)


def load_validated_configuration(
    config_path: Path,
    project_id_override: str | None = None,
) -> tuple[dict[str, Any], str, dict[str, str]]:
    if not config_path.exists():
        raise FileNotFoundError(f"Missing BigQuery configuration: {config_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("BigQuery configuration must be a YAML mapping.")

    configured_project_id = config.get("project_id")
    environment_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

    if project_id_override is not None:
        project_id = project_id_override
    elif environment_project_id:
        project_id = environment_project_id
    else:
        project_id = configured_project_id

    datasets = config.get("datasets")
    validate_bigquery_identifiers(
        project_id,
        datasets,
        table_names=config.get("tables", {}).keys(),
    )

    return config, project_id, dict(datasets)


def current_pipeline_run_id() -> str:
    pipeline_run_id = _PIPELINE_RUN_ID.get()
    if pipeline_run_id is None:
        raise RuntimeError("No active pipeline run ID is available.")
    return pipeline_run_id


def current_pipeline_started_at() -> datetime:
    started_at = _PIPELINE_STARTED_AT.get()
    if started_at is None:
        raise RuntimeError("No active pipeline start time is available.")
    return started_at


def current_pipeline_configuration() -> dict[str, Any]:
    config = _PIPELINE_CONFIG.get()
    if config is None:
        raise RuntimeError("No active pipeline configuration is available.")
    return config


def current_pipeline_project_id() -> str:
    project_id = _PIPELINE_PROJECT_ID.get()
    if project_id is None:
        raise RuntimeError("No active pipeline project ID is available.")
    return project_id


def current_pipeline_datasets() -> dict[str, str]:
    datasets = _PIPELINE_DATASETS.get()
    if datasets is None:
        raise RuntimeError("No active pipeline dataset mapping is available.")
    return datasets


def current_pipeline_loaded_table_count() -> int:
    return _PIPELINE_LOADED_TABLE_COUNT.get()


def set_pipeline_loaded_table_count(table_count: int) -> None:
    if table_count < 0:
        raise ValueError("Loaded table count cannot be negative.")
    _PIPELINE_LOADED_TABLE_COUNT.set(table_count)


def _load_bound_configuration(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[dict[str, Any], str, dict[str, str]]:
    bound = signature(function).bind_partial(*args, **kwargs)
    config_path = Path(bound.arguments["config_path"])
    project_id_override = bound.arguments.get("project_id_override")
    return load_validated_configuration(config_path, project_id_override)


def _load_failure_destination(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[str, str]:
    try:
        project_id = current_pipeline_project_id()
        datasets = current_pipeline_datasets()
    except RuntimeError:
        _, project_id, datasets = _load_bound_configuration(
            function,
            args,
            kwargs,
        )

    return project_id, datasets["control"]


def _attach_logging_note(original_error: Exception, message: str) -> None:
    add_note = getattr(original_error, "add_note", None)
    if add_note is not None:
        add_note(message)


def _write_failure_row(
    *,
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    pipeline_run_id: str,
    pipeline_name: str,
    started_at: datetime,
    error: Exception,
) -> None:
    try:
        project_id, control_dataset = _load_failure_destination(
            function,
            args,
            kwargs,
        )
        client = bigquery.Client(project=project_id)
        completed_at = datetime.now(timezone.utc)

        insert_errors = client.insert_rows_json(
            f"{project_id}.{control_dataset}.pipeline_run_log",
            [
                {
                    "pipeline_run_id": pipeline_run_id,
                    "pipeline_name": pipeline_name,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "status": "FAIL",
                    "loaded_table_count": current_pipeline_loaded_table_count(),
                    "error_message": str(error)[:1000],
                }
            ],
        )

        if insert_errors:
            _attach_logging_note(
                error,
                "Failure occurred, and writing the pipeline failure log also "
                f"returned errors: {insert_errors}",
            )

    except Exception as logging_error:
        _attach_logging_note(
            error,
            "Failure occurred, and the pipeline failure log could not be written: "
            f"{logging_error}",
        )


def pipeline_run_guard(
    pipeline_name: str,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            pipeline_run_id = str(uuid.uuid4())
            started_at = datetime.now(timezone.utc)

            run_id_token = _PIPELINE_RUN_ID.set(pipeline_run_id)
            started_at_token = _PIPELINE_STARTED_AT.set(started_at)
            loaded_count_token = _PIPELINE_LOADED_TABLE_COUNT.set(0)
            config_token = None
            project_token = None
            datasets_token = None

            try:
                config, project_id, datasets = _load_bound_configuration(
                    function,
                    args,
                    kwargs,
                )
                config_token = _PIPELINE_CONFIG.set(config)
                project_token = _PIPELINE_PROJECT_ID.set(project_id)
                datasets_token = _PIPELINE_DATASETS.set(datasets)
                return function(*args, **kwargs)
            except Exception as error:
                _write_failure_row(
                    function=function,
                    args=args,
                    kwargs=kwargs,
                    pipeline_run_id=pipeline_run_id,
                    pipeline_name=pipeline_name,
                    started_at=started_at,
                    error=error,
                )
                raise
            finally:
                if datasets_token is not None:
                    _PIPELINE_DATASETS.reset(datasets_token)
                if project_token is not None:
                    _PIPELINE_PROJECT_ID.reset(project_token)
                if config_token is not None:
                    _PIPELINE_CONFIG.reset(config_token)
                _PIPELINE_LOADED_TABLE_COUNT.reset(loaded_count_token)
                _PIPELINE_STARTED_AT.reset(started_at_token)
                _PIPELINE_RUN_ID.reset(run_id_token)

        return wrapper

    return decorator
