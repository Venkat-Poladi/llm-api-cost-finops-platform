from pathlib import Path

import yaml


def test_project_configuration_exists() -> None:
    config_path = Path("config/project_config.yaml")
    assert config_path.exists()

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["project"]["reporting_currency"] == "USD"
    assert config["project"]["history_months"] == 18
    assert set(config["providers"]) == {"openai", "anthropic"}
