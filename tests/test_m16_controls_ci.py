from pathlib import Path

import yaml


REGISTRY_PATH = Path("config/control_registry.yaml")
CONFIG_PATH = Path("config/m16_bigquery.yaml")


def load_registry() -> dict:
    assert REGISTRY_PATH.exists(), "control_registry.yaml is missing"
    return yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "m16_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m16_registry_has_exactly_18_unique_controls() -> None:
    controls = load_registry()["controls"]
    control_ids = [control["control_id"] for control in controls]

    assert len(controls) == 18
    assert len(control_ids) == len(set(control_ids))


def test_m16_control_ids_are_ordered_and_complete() -> None:
    control_ids = [
        control["control_id"]
        for control in load_registry()["controls"]
    ]

    assert control_ids == [
        f"E2E-{number:02d}"
        for number in range(1, 19)
    ]


def test_every_control_has_required_metadata() -> None:
    required = {
        "control_id",
        "control_name",
        "control_domain",
        "severity",
        "data_layer",
        "description",
    }

    for control in load_registry()["controls"]:
        assert required <= set(control)
        assert all(str(control[field]).strip() for field in required)
        assert control["severity"] == "CRITICAL"


def test_m16_uses_expected_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m16_requires_all_previous_cloud_pipelines() -> None:
    pipelines = load_config()["expected_previous_pipelines"]

    assert len(pipelines) == 10
    assert pipelines[0] == "M6_BIGQUERY_RAW_LAYER"
    assert pipelines[-1] == "M15_EXPERIMENT_GOVERNANCE"


def test_m16_creates_four_control_objects() -> None:
    objects = load_config()["expected_objects"]

    assert len(objects) == 4
    assert len(objects) == len(set(objects))
    assert "llm_finops_mart.mart_ai_control_status" in objects
    assert "llm_finops_mart.mart_ai_pipeline_status" in objects


def test_m16_sql_files_exist() -> None:
    for relative_path in load_config()["sql_files"]:
        assert Path(relative_path).exists(), f"{relative_path} is missing"


def test_repository_ci_runs_compile_tests_and_ruff() -> None:
    script = Path("scripts/run_repo_ci.py").read_text(encoding="utf-8")

    assert "compileall" in script
    assert '"-m", "pytest"' in script
    assert '"-m", "ruff", "check", "."' in script


def test_github_quality_workflow_runs_repository_ci() -> None:
    workflow = Path(
        ".github/workflows/quality.yml"
    ).read_text(encoding="utf-8")

    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "python scripts/run_repo_ci.py" in workflow


def test_m16_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m16.py").exists()
    assert Path("scripts/run_m16.ps1").exists()
