# Trainings

One file per training, `configs/trainings/<name>.yaml` (design doc change 24).
Merging a new file to `main` trains a model on the dataset's labels with no
round; the file stays as its record. Start from the platform's example
([configs/examples/training.yaml](https://github.com/duytq5/duytq5-leaf-al-platform/blob/main/configs/examples/training.yaml)):

```yaml
dataset: rocole
# version: 3  # dataset version to train on; default: the latest
train:
  recipe: timm_classifier
  params: {epochs: 20}
  # base_model: models:/rocole-fastvit@champion  # fine-tune from a registered model
```

CI runs the pinned platform's `al check-training` on every file. The model is
registered in MLflow and recorded in `model_versions`; rounds without a
`train` section then score with it, and a release file can ship it to the app.
A training changes no data, so it can run while a round waits for labels.
