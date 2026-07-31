from __future__ import annotations

from collections.abc import Iterable, Mapping
import re


_PROJECT_ID_PATTERN = re.compile(
    r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
)
_STANDARD_IDENTIFIER_PATTERN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]{0,1023}"
)


def _display(value: object) -> str:
    rendered = repr(value)

    if len(rendered) > 120:
        return f"{rendered[:117]}..."

    return rendered


def validate_project_id(project_id: str) -> None:
    if (
        not isinstance(project_id, str)
        or _PROJECT_ID_PATTERN.fullmatch(project_id) is None
    ):
        raise ValueError(
            "Unsafe BigQuery project ID for this repository: "
            f"{_display(project_id)}. Expected 6-30 lowercase "
            "letters, digits, or hyphens; it must start with a "
            "letter and end with a letter or digit."
        )


def validate_dataset_id(
    dataset_id: str,
    *,
    label: str = "dataset",
) -> None:
    if (
        not isinstance(dataset_id, str)
        or _STANDARD_IDENTIFIER_PATTERN.fullmatch(dataset_id) is None
    ):
        raise ValueError(
            f"Unsafe BigQuery {label} ID for this repository: "
            f"{_display(dataset_id)}. Use letters, digits, and "
            "underscores only, beginning with a letter or underscore."
        )


def validate_table_id(
    table_id: str,
    *,
    label: str = "table",
) -> None:
    if (
        not isinstance(table_id, str)
        or _STANDARD_IDENTIFIER_PATTERN.fullmatch(table_id) is None
    ):
        raise ValueError(
            f"Unsafe BigQuery {label} ID for this repository: "
            f"{_display(table_id)}. Use letters, digits, and "
            "underscores only, beginning with a letter or underscore."
        )


def validate_bigquery_identifiers(
    project_id: str,
    datasets: Mapping[str, str],
    *,
    table_names: Iterable[str] = (),
) -> None:
    validate_project_id(project_id)

    if not isinstance(datasets, Mapping) or not datasets:
        raise ValueError(
            "BigQuery dataset configuration must be a non-empty mapping."
        )

    for layer, dataset_id in datasets.items():
        if not isinstance(layer, str) or not layer:
            raise ValueError(
                "BigQuery dataset layer names must be non-empty strings."
            )

        validate_dataset_id(
            dataset_id,
            label=f"dataset for layer {layer!r}",
        )

    for table_name in table_names:
        validate_table_id(table_name)
