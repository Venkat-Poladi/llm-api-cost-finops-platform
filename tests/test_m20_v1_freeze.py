from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_m20_release_documents_exist() -> None:
    required = [
        "docs/releases/v1.0.0.md",
        "docs/releases/v1_metric_baseline.md",
        "docs/releases/v1_capability_status.md",
        "docs/releases/v1_reconciliation_evidence.md",
        "docs/metric_change_log.md",
        "docs/v2_build_plan.md",
        "docs/v2_known_limitations.md",
        "docs/capability_status.md",
        "evidence/releases/v1.0.0/generation_manifest.json",
        "evidence/releases/v1.0.0/repository_validation.txt",
        "evidence/releases/v1.0.0/powerbi_artifact_hashes.sha256",
    ]
    assert all((ROOT / path).is_file() for path in required)


def test_v1_manifest_freezes_deterministic_baseline() -> None:
    manifest = json.loads(
        (ROOT / "evidence/releases/v1.0.0/generation_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["generator_version"] == "1.0.0"
    assert manifest["master_seed"] == 42
    assert manifest["files"]["raw_ai_provider_usage.csv"]["row_count"] == 4431
    assert manifest["files"]["raw_ai_provider_cost.csv"]["row_count"] == 135
    assert (
        manifest["files"]["raw_ai_provider_cost.csv"]["invoice_billed_cost"]
        == 20340.146796
    )
    assert (
        manifest["files"]["raw_ai_provider_cost.csv"]["provider_reported_cost"]
        == 20243.727255
    )
    telemetry = manifest["files"]["fct_ai_request_telemetry.csv"]
    assert telemetry["row_count"] == 369921
    assert telemetry["logical_request_count"] == 347775
    assert telemetry["retry_attempt_count"] == 22146


def test_tracker_and_readme_agree_on_release_status() -> None:
    tracker = (ROOT / "docs/milestone_tracker.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    status = (ROOT / "docs/capability_status.md").read_text(encoding="utf-8")
    for milestone in range(0, 21):
        assert f"M{milestone} —" in tracker
    assert "M20 — Freeze and Release v1 | Complete" in tracker
    for milestone in range(21, 36):
        assert f"M{milestone} —" in tracker
    assert "v1.0.0 complete" in readme
    assert "Release tag | `v1.0.0`" in status
    assert "Phase 2 implementation | Planned; not yet implemented" in status


def test_phase_2_plan_locks_only_the_approved_budget() -> None:
    plan = (ROOT / "docs/v2_build_plan.md").read_text(encoding="utf-8")
    assert "$76,438.52" in plan
    assert "Actual cost, forecast, variances, opportunities" in plan
    assert "must not be manually targeted" in plan
    assert "M21 —" in plan
    assert "M35 —" in plan


def test_powerbi_release_hashes_match_committed_artifacts() -> None:
    hash_file = ROOT / "evidence/releases/v1.0.0/powerbi_artifact_hashes.sha256"
    for line in hash_file.read_text(encoding="utf-8").splitlines():
        expected, relative_path = line.split("  ", maxsplit=1)
        artifact = ROOT / relative_path
        assert artifact.is_file(), relative_path
        payload = artifact.read_bytes()
        if artifact.suffix.lower() != ".png":
            payload = payload.replace(b"\r\n", b"\n")
        actual = hashlib.sha256(payload).hexdigest()
        assert actual == expected, relative_path


def test_v1_baseline_preserves_claim_boundaries() -> None:
    baseline = (ROOT / "docs/releases/v1_metric_baseline.md").read_text(
        encoding="utf-8"
    )
    limitations = (ROOT / "docs/v2_known_limitations.md").read_text(
        encoding="utf-8"
    )
    assert "identified and modeled opportunity" in baseline
    assert "not actual company savings" in baseline
    assert "No actual business ROI" in limitations
    assert "No autonomous AI FinOps agent" in limitations
