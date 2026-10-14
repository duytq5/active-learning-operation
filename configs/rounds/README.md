# AL rounds

One file per round, `configs/rounds/<name>.yaml` (design doc F3). Merging a new
file to `main` starts that round; the file stays as its record. Start from the
platform's example
([configs/examples/round.yaml](https://github.com/duytq5/duytq5-leaf-al-platform/blob/main/configs/examples/round.yaml)):

```yaml
dataset: rocole
# base_version: 0  # dataset version to train on; default: the latest
train:
  recipe: timm_classifier
  params: {epochs: 20}
  # base_model: models:/rocole-fastvit@champion  # fine-tune from a registered model
selection:
  strategy: random
  params: {}
  k: 50
  seed: 42
```

A round without `train` only selects (no training): it scores the pool with
`model: models:/<name>/<version>` (or `@alias`), or by default with the
dataset's newest model, then labels and merges as usual. Train later with a
file in [configs/trainings/](../trainings/README.md). The longer training
waits, the staler the scores, and uncertainty strategies drift toward random.

CI runs the pinned platform's `al check-round` on every file. List recipes and
strategies with their parameters from a platform checkout: `uv run al recipes`,
`uv run al strategies`. A dataset takes one round at a time: a new file for a
dataset with an unfinished round is refused (red check on the merge commit).
