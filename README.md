# active-learning-operation

Operations for the leaf-disease active-learning platform
([duytq5/duytq5-leaf-al-platform](https://github.com/duytq5/duytq5-leaf-al-platform)).
Every change to the running system is a pull request here: GitHub records who
proposed it, who approved it and who merged it. The platform repo holds the
code; this repo holds what the system is told to do.

| Path | What it does when it merges to `main` |
| --- | --- |
| `configs/releases/{dataset}.yaml` | Releases that model version to the app (workflow `release`) |
| `platform.yaml` | Moves rounds and releases to newer platform code |

Starting and cancelling rounds (`configs/rounds/`) arrives with the platform's
round-control PR.

## Release or roll back a model

1. Turn the GPU worker on: the release exports the model to ONNX on it.
2. Open a PR that sets `model` and `version` in `configs/releases/<dataset>.yaml`
   (see [configs/releases/README.md](configs/releases/README.md)). CI checks
   the file against the pinned platform's dataset configs.
3. Merge it. The `release` workflow starts the `model-release` state machine
   and waits for it; the commit's check shows whether it worked, and the run's
   summary lists each execution. The app gets the new version on its next
   `GET /v1/devices/config`.

To roll back, revert the release commit. The same path runs, skips the export
(the earlier files are still there) and records a `rollback`.

## Platform version

`platform.yaml` names one platform commit. The workflows check out that
commit and run its `al` CLI, and rounds will run in its worker image. To use
newer platform code, change the commit in a PR.

## Setup (once)

- Repository variable `AWS_ROLE_ARN` (Settings, Secrets and variables,
  Actions, Variables): the platform stack's `GithubActionsRoleArn` output. It
  names the role and grants nothing by itself; only runs on `main` of this
  repo may assume the role. No AWS keys are stored here.
- Branch protection on `main`: require a pull request, CI green and review
  from Code Owners (`.github/CODEOWNERS`).
