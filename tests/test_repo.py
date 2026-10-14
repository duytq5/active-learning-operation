"""Checks on this repo's workflows and files. CI runs them with the pinned
platform's environment (`uv run --project platform pytest tests`)."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
PLATFORM_REPO = "duytq5/duytq5-leaf-al-platform"


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if True in data:
        data["on"] = data.pop(True)  # YAML 1.1 reads the key `on` as true
    return data


def _run_lines(steps: list[dict]) -> str:
    return "\n".join(step.get("run", "") for step in steps)


def _uses(steps: list[dict]) -> list[str]:
    return [step["uses"] for step in steps if "uses" in step]


# platform.yaml and the action that checks the pinned platform out


def test_platform_pins_one_commit():
    pin = yaml.safe_load((ROOT / "platform.yaml").read_text())
    assert set(pin) == {"commit"}
    assert re.fullmatch(r"[0-9a-f]{40}", pin["commit"])


def test_platform_action_checks_out_the_pinned_commit():
    action = _load(ROOT / ".github/actions/platform/action.yml")
    steps = action["runs"]["steps"]
    assert action["runs"]["using"] == "composite"
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["repository"] == PLATFORM_REPO
    assert checkout["with"]["path"] == "platform"
    assert "steps.pin.outputs.commit" in checkout["with"]["ref"]
    run = _run_lines(steps)
    assert "platform.yaml" in run
    assert "uv sync --locked --project platform" in run


def test_platform_checkout_is_not_committed():
    assert "platform/" in (ROOT / ".gitignore").read_text().split()


# CI on every pull request


def test_ci_validates_releases_against_the_platform_datasets():
    wf = _load(WORKFLOWS / "ci.yml")
    assert "pull_request" in wf["on"]
    (job,) = wf["jobs"].values()
    assert "./.github/actions/platform" in _uses(job["steps"])
    run = _run_lines(job["steps"])
    assert (
        "uv run --project platform al check-release --datasets platform/configs/datasets" in run
    )
    assert "uv run --project platform pytest tests" in run
    # CI never gets AWS access: pull requests can come from anyone.
    assert "id-token" not in wf.get("permissions", {})


# release (design doc F5)


def test_release_runs_on_merges_to_release_files():
    wf = _load(WORKFLOWS / "release.yml")
    assert wf["on"]["push"] == {"branches": ["main"], "paths": ["configs/releases/**"]}
    # Only an OIDC token and a read of the repo; no stored AWS keys.
    assert wf["permissions"] == {"id-token": "write", "contents": "read"}
    # Two quick merges: the newer one waits, nothing runs side by side.
    assert wf["concurrency"] == {"group": "release", "cancel-in-progress": False}


def test_release_job_assumes_the_role_and_waits():
    (job,) = _load(WORKFLOWS / "release.yml")["jobs"].values()
    assert job["timeout-minutes"] == 360
    assert "./.github/actions/platform" in _uses(job["steps"])
    creds = next(s for s in job["steps"] if "configure-aws-credentials" in s.get("uses", ""))
    assert creds["with"]["role-to-assume"] == "${{ vars.AWS_ROLE_ARN }}"
    assert creds["with"]["aws-region"] == "ap-southeast-2"
    run = _run_lines(job["steps"])
    assert "uv run --project platform al release-input" in run
    assert "stepfunctions start-execution" in run
    assert "stepfunctions describe-execution" in run
    assert "/leaf-al/state-machines/model-release" in run


# all workflows


def test_no_secrets_and_pinned_actions():
    paths = [*WORKFLOWS.glob("*.yml"), ROOT / ".github/actions/platform/action.yml"]
    for path in paths:
        assert "secrets." not in path.read_text(), path.name
        data = _load(path)
        jobs = data.get("jobs", {"action": data.get("runs", {})})
        for job in jobs.values():
            for uses in _uses(job.get("steps", [])):
                assert uses.startswith("./") or "@" in uses, (path.name, uses)


def test_codeowners_name_the_operator_paths():
    owners = (ROOT / ".github/CODEOWNERS").read_text()
    for path in ("*", "/configs/releases/", "/configs/rounds/", "/platform.yaml", "/.github/"):
        assert re.search(rf"^{re.escape(path)}\s+@\w", owners, re.M), path
