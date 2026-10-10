"""Shared body for the per-model training scripts.

``train_random_forest.py``, ``train_xgboost.py`` and ``train_mlp.py`` are thin
argparse wrappers around :func:`main`. Each one:

  1. loads the same combined dataset the deployed SVM was trained on
  2. selects hyperparameters with subject-grouped ``GroupKFold`` over all of it
  3. saves that fitted model as a versioned artifact
  4. reports **nested** LOSO metrics - hyperparameters re-selected inside every
     outer fold, so the reported number never saw its own test subject

Step 2 and step 4 are deliberately different searches. Step 2 produces the
artifact that ships; step 4 produces the number that gets quoted. Conflating
them is how a model ends up reported with hyperparameters that were chosen
using its own test subject.

The cross-model comparison (and the ensembles) live in
``scripts/train_all_models.py``, which shares this work across all candidates
in one pass instead of repeating it per model.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config  # noqa: E402
from stress_detection.models.dataset import load_combined_dataset  # noqa: E402
from stress_detection.models.evaluation import nested_loso_single_model  # noqa: E402
from stress_detection.models.training import (  # noqa: E402
    fit_base_model,
    save_single_model,
    write_json,
)

logger = logging.getLogger(__name__)


def build_parser(model_name: str, artifact_stem: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Train and evaluate the {model_name} stress classifier."
    )
    parser.add_argument(
        "--version", default="v3",
        help="Version tag for the artifact and metrics filenames (default: v3).",
    )
    parser.add_argument(
        "--no-tune", action="store_true",
        help="Skip the grid search and use the module's default hyperparameters.",
    )
    parser.add_argument(
        "--skip-loso", action="store_true",
        help="Fit and save the artifact without running the nested LOSO evaluation.",
    )
    parser.add_argument(
        "--tune-splits", type=int, default=3,
        help="Inner GroupKFold splits used inside each outer LOSO fold (default: 3).",
    )
    parser.set_defaults(model_name=model_name, artifact_stem=artifact_stem)
    return parser


def main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    name, version = args.model_name, args.version
    cfg = get_config()

    dataset = load_combined_dataset()
    print(
        f"\nDataset: {dataset.n_windows:,} windows, {dataset.n_subjects} subjects, "
        f"{len(dataset.feature_names)} features"
    )

    print(f"\nFitting {name} on all subjects (GroupKFold hyperparameter search)...")
    fitted = fit_base_model(name, dataset, tune=not args.no_tune)
    print(f"  params:    {fitted.params or '(module defaults)'}")
    if fitted.cv_score is not None:
        print(f"  grouped CV f1_macro (selection statistic, not a result): {fitted.cv_score:.4f}")

    artifact = cfg.paths.data_models / f"{args.artifact_stem}_{version}.joblib"
    save_single_model(fitted, dataset, artifact, model_version=version)
    print(f"  artifact:  {artifact}")

    if args.skip_loso:
        print("\nSkipping LOSO evaluation (--skip-loso).")
        return

    print(f"\nNested LOSO over {dataset.n_subjects} subjects (this refits per fold)...")
    result = nested_loso_single_model(
        name, dataset.X, dataset.y, dataset.groups, tune_splits=args.tune_splits,
    )
    pooled = result["pooled"]
    print(f"\n=== {name} - nested LOSO ({result['n_folds']} folds) ===")
    print(f"Accuracy:   {pooled['accuracy']:.3f}  (per-subject {result['accuracy_mean']:.3f} ± {result['accuracy_std']:.3f})")
    print(f"Macro F1:   {pooled['macro_f1']:.3f}  (per-subject {result['macro_f1_mean']:.3f} ± {result['macro_f1_std']:.3f})")
    print(f"Stress F1:  {pooled['stress_f1']:.3f}")
    print(f"ROC-AUC:    {pooled['roc_auc']:.3f}" if pooled["roc_auc"] is not None else "ROC-AUC:    n/a")
    print(f"Confusion:  {pooled['confusion_matrix']}")

    payload = {
        "model": name,
        "version": version,
        "artifact": str(artifact),
        "deployment_params": fitted.params,
        "deployment_grouped_cv_f1_macro": fitted.cv_score,
        "dataset": dataset.summary(),
        **{k: v for k, v in result.items() if k not in ("probabilities", "predictions")},
    }
    metrics_path = cfg.paths.reports / f"metrics_{args.artifact_stem}_{version}.json"
    write_json(payload, metrics_path)
    print(f"\nMetrics → {metrics_path}")
