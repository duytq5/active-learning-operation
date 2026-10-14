# active-learning-operation

Operations for the leaf-disease active-learning platform
([duytq5/duytq5-leaf-al-platform](https://github.com/duytq5/duytq5-leaf-al-platform)).
Every change to the running system is a pull request here: GitHub records who
proposed it, who approved it and who merged it. The platform repo holds the
code; this repo holds what the system is told to do.

| Path | What it does when it merges to `main` |
| --- | --- |
| `configs/rounds/<name>.yaml` (new file) | Starts that AL round (workflow `start-round`) |
| `configs/trainings/<name>.yaml` (new file) | Trains a model on the dataset's labels, with no round (workflow `start-training`) |
| `configs/releases/{dataset}.yaml` | Releases that model version to the app (workflow `release`) |
| `platform.yaml` | Moves rounds and releases to newer platform code |

## Start or cancel a round

1. Turn the GPU worker on: it trains and scores the round.
2. Open a PR adding `configs/rounds/<name>.yaml` (see
   [configs/rounds/README.md](configs/rounds/README.md)). CI runs
   `al check-round` on it with the pinned platform.
3. Merge it. The `start-round` workflow checks that the pinned platform
   commit has a worker image, asks the platform to validate and insert the
   round, and starts the `al-round` execution. A refused round turns the
   commit's check red; the run's summary names the round id.
4. Watch it with `GET /v1/rounds/active`, label in Label Studio when the round
   asks for labels, and compare runs in MLflow.

To cancel: Actions, cancel-round, Run workflow, with the round id. The round
becomes `cancelled` and its selected images go back to the pool.

## Rounds without training, then train later

A round file without `train` only selects: it scores the pool with an
existing model (`model:`, or the dataset's newest model) and trains nothing,
so you can run several rounds in a row. When you want a new model, add
`configs/trainings/<name>.yaml` (see
[configs/trainings/README.md](configs/trainings/README.md)); merging it trains
on the dataset's latest version. Turn the GPU worker on first. A training does
not block rounds.

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
commit and run its `al` CLI, and rounds run in its worker image
(`ghcr.io/duytq5/duytq5-leaf-al-platform-worker:<commit>`). The platform
builds an image only for commits on its `main`, so pin a commit from the
platform's `main` history whose `worker-image` run passed. To use newer
platform code, change the commit in a PR.

## Setup (once)

- Repository variable `AWS_ROLE_ARN` (Settings, Secrets and variables,
  Actions, Variables): the platform stack's `GithubActionsRoleArn` output. It
  names the role and grants nothing by itself; only runs on `main` of this
  repo may assume the role. No AWS keys are stored here.
- Branch protection on `main`: require a pull request, CI green and review
  from Code Owners (`.github/CODEOWNERS`).
