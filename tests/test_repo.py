"""Checks on this repo's workflows and files. CI runs them with the pinned
platform's environment (`uv run --project platform pytest tests`)."""

import re
import subprocess
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
    checkout = next(
        s for s in steps if s.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["repository"] == PLATFORM_REPO
    assert checkout["with"]["path"] == "platform"
    assert "steps.pin.outputs.commit" in checkout["with"]["ref"]
    run = _run_lines(steps)
    assert "platform.yaml" in run
    assert "uv sync --locked --project platform" in run


def test_platform_checkout_is_not_committed():
    # Anchored: a bare `platform/` would also ignore .github/actions/platform/.
    assert "/platform/" in (ROOT / ".gitignore").read_text().split()


def test_platform_action_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", ".github/actions/platform/action.yml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == ".github/actions/platform/action.yml"


# CI on every pull request


def test_ci_validates_releases_against_the_platform_datasets():
    wf = _load(WORKFLOWS / "ci.yml")
    assert "pull_request" in wf["on"]
    (job,) = wf["jobs"].values()
    assert "./.github/actions/platform" in _uses(job["steps"])
    run = _run_lines(job["steps"])
    assert (
        "uv run --project platform al check-release --datasets platform/configs/datasets"
        in run
    )
    assert "uv run --project platform pytest tests" in run
    # Every round file is checked, against the platform's dataset configs.
    assert "configs/rounds/*.yaml" in run
    assert "al check-round" in run and "--datasets platform/configs/datasets" in run
    # Every training file too (design doc change 24).
    assert "configs/trainings/*.yaml" in run and "al check-training" in run
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
    creds = next(
        s for s in job["steps"] if "configure-aws-credentials" in s.get("uses", "")
    )
    assert creds["with"]["role-to-assume"] == "${{ vars.AWS_ROLE_ARN }}"
    assert creds["with"]["aws-region"] == "ap-southeast-2"
    run = _run_lines(job["steps"])
    assert "uv run --project platform al release-input" in run
    assert "stepfunctions start-execution" in run
    assert "stepfunctions describe-execution" in run
    assert "/leaf-al/state-machines/model-release" in run


# start-round and cancel-round (design doc F3)


def test_start_round_runs_on_merges_to_round_files():
    wf = _load(WORKFLOWS / "start-round.yml")
    assert wf["on"]["push"] == {"branches": ["main"], "paths": ["configs/rounds/**"]}
    assert wf["permissions"] == {"id-token": "write", "contents": "read"}
    assert wf["concurrency"] == {"group": "start-round", "cancel-in-progress": False}


def test_start_round_uses_the_pinned_platform_image():
    (job,) = _load(WORKFLOWS / "start-round.yml")["jobs"].values()
    steps = job["steps"]
    platform = next(s for s in steps if s.get("uses") == "./.github/actions/platform")
    assert platform["id"] == "platform"
    # A job's env cannot read step outputs, so a step exports the image.
    assert "env" not in job
    image = next(s for s in steps if s.get("name") == "Worker image")
    assert image["env"]["COMMIT"] == "${{ steps.platform.outputs.commit }}"
    assert (
        'IMAGE=ghcr.io/duytq5/duytq5-leaf-al-platform-worker:$COMMIT' in image["run"]
    )
    assert '>> "$GITHUB_ENV"' in image["run"]
    run = _run_lines(steps)
    # A pin without an image (not a main commit, or its build failed) stops
    # here, before AWS is touched.
    assert 'docker manifest inspect "$IMAGE"' in run
    assert "al check-round" in run and "--datasets platform/configs/datasets" in run
    creds = next(s for s in steps if "configure-aws-credentials" in s.get("uses", ""))
    assert creds["with"]["role-to-assume"] == "${{ vars.AWS_ROLE_ARN }}"
    assert creds["with"]["aws-region"] == "ap-southeast-2"
    assert 'uv run --project platform al round-input "$file"' in run
    assert '--image "$IMAGE"' in run
    assert "lambda invoke --function-name leaf-al-start-round" in run
    assert "stepfunctions start-execution" in run
    assert "ExecutionAlreadyExists" in run
    assert "/leaf-al/state-machines/al-round" in run


# start-training (design doc change 24)


def test_start_training_runs_on_merges_to_training_files():
    wf = _load(WORKFLOWS / "start-training.yml")
    assert wf["on"]["push"] == {"branches": ["main"], "paths": ["configs/trainings/**"]}
    assert wf["permissions"] == {"id-token": "write", "contents": "read"}
    assert wf["concurrency"] == {"group": "start-training", "cancel-in-progress": False}


def test_start_training_uses_the_pinned_platform_image():
    (job,) = _load(WORKFLOWS / "start-training.yml")["jobs"].values()
    steps = job["steps"]
    platform = next(s for s in steps if s.get("uses") == "./.github/actions/platform")
    assert platform["id"] == "platform"
    image = next(s for s in steps if s.get("name") == "Worker image")
    assert image["env"]["COMMIT"] == "${{ steps.platform.outputs.commit }}"
    assert 'docker manifest inspect "$IMAGE"' in image["run"]
    creds = next(s for s in steps if "configure-aws-credentials" in s.get("uses", ""))
    assert creds["with"]["role-to-assume"] == "${{ vars.AWS_ROLE_ARN }}"
    assert creds["with"]["aws-region"] == "ap-southeast-2"
    run = _run_lines(steps)
    assert "configs/trainings/*.yaml" in run
    assert "al check-training" in run and "--datasets platform/configs/datasets" in run
    assert 'uv run --project platform al round-input "$file"' in run
    assert "lambda invoke --function-name leaf-al-start-training" in run
    assert "stepfunctions start-execution" in run and "ExecutionAlreadyExists" in run
    assert "/leaf-al/state-machines/al-train" in run
    assert ".training_id" in run


def test_cancel_round_is_a_manual_run_with_a_round_id():
    wf = _load(WORKFLOWS / "cancel-round.yml")
    assert set(wf["on"]) == {"workflow_dispatch"}
    assert wf["on"]["workflow_dispatch"]["inputs"]["round_id"]["required"] is True
    assert wf["permissions"] == {"id-token": "write", "contents": "read"}
    (job,) = wf["jobs"].values()
    run = _run_lines(job["steps"])
    assert "stepfunctions stop-execution" in run
    assert "lambda invoke --function-name leaf-al-cancel-round" in run
    # The input lands in a shell variable, never pasted into the script.
    assert "${{ inputs.round_id }}" not in run


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
    for path in (
        "*",
        "/configs/releases/",
        "/configs/rounds/",
        "/configs/trainings/",
        "/platform.yaml",
        "/.github/",
    ):
        assert re.search(rf"^{re.escape(path)}\s+@\w", owners, re.M), path
