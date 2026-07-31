from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from inspect import signature
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar
import uuid

import yaml
from google.cloud import bigquery

from llm_finops.bigquery.identifiers import (
    validate_bigquery_identifiers,
)


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


def _load_bound_configuration(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    bound = signature(function).bind_partial(*args, **kwargs)
    config_path = Path(bound.arguments["config_path"])
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    project_id_override = bound.arguments.get("project_id_override")
    project_id = project_id_override or config["project_id"]
    datasets = config["datasets"]

    validate_bigquery_identifiers(project_id, datasets)

    return project_id, datasets


def _load_failure_destination(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[str, str]:
    project_id, datasets = _load_bound_configuration(
        function,
        args,
        kwargs,
    )

    return project_id, datasets["control"]


def _attach_logging_note(
    original_error: Exception,
    message: str,
) -> None:
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
                    "loaded_table_count": 0,
                    "error_message": str(error)[:1000],
                }
            ],
        )

        if insert_errors:
            _attach_logging_note(
                error,
                "Failure occurred, and writing the pipeline failure "
                f"log also returned errors: {insert_errors}",
            )

    except Exception as logging_error:
        _attach_logging_note(
            error,
            "Failure occurred, and the pipeline failure log could "
            f"not be written: {logging_error}",
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

            try:
                _load_bound_configuration(
                    function,
                    args,
                    kwargs,
                )
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
                _PIPELINE_RUN_ID.reset(run_id_token)
                _PIPELINE_STARTED_AT.reset(started_at_token)

        return wrapper

    return decorator
