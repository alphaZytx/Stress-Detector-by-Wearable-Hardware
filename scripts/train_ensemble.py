"""Build the two ensemble artifacts from freshly tuned base models.

Usage:
    python3 scripts/train_ensemble.py [--version v3] [--no-tune] [--soft-weighting equal|derived]

Outputs:
    data/models/ensemble_soft_<version>.joblib
    data/models/ensemble_stack_<version>.joblib
    reports/metrics_ensemble_artifacts_<version>.json

This script produces *deployable artifacts*, fitted on every available subject.
It does not produce performance numbers: an artifact fitted on all subjects has
no held-out subject left to score against. The comparison lives in
``scripts/train_all_models.py`` / ``scripts/evaluate_models.py``, which run the
nested LOSO protocol.

The stacking artifact is still built leakage-safely - its meta-model is trained
on grouped out-of-fold probabilities, never on in-sample ones - because a
meta-model fitted on optimistic base predictions would be miscalibrated at
serving time too, not just mis-measured.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config  # noqa: E402
from stress_detection.models.common import BASE_MODEL_NAMES  # noqa: E402
from stress_detection.models.dataset import load_combined_dataset  # noqa: E402
from stress_detection.models.training import (  # noqa: E402
    benchmark_latency,
    derive_soft_voting_weights,
    fit_all_base_models,
    fit_soft_voting,
    fit_stacking,
    save_ensemble,
    write_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the soft-voting and stacking artifacts.")
    parser.add_argument("--version", default="v3", help="Artifact version tag (default: v3).")
    parser.add_argument(
        "--no-tune", action="store_true",
        help="Use the module default hyperparameters instead of a grid search.",
    )
    parser.add_argument(
        "--soft-weighting", choices=("equal", "derived"), default="equal",
        help="Soft-voting weights for the saved artifact. 'equal' (default) is "
             "the primary baseline; 'derived' uses grouped-OOF ROC-AUC weights.",
    )
    parser.add_argument(
        "--oof-splits", type=int, default=5,
        help="Grouped folds used to build the stacking meta-features (default: 5).",
    )
    args = parser.parse_args()

    cfg = get_config()
    dataset = load_combined_dataset()
    print(
        f"\nDataset: {dataset.n_windows:,} windows, {dataset.n_subjects} subjects, "
        f"{len(dataset.feature_names)} features"
    )

    print("\nFitting base models (subject-grouped hyperparameter search)...")
    fitted = fit_all_base_models(dataset, tune=not args.no_tune)
    for name, model in fitted.items():
        print(f"  {name:15s} {model.params or '(defaults)'}")

    weights = None
    if args.soft_weighting == "derived":
        weights = derive_soft_voting_weights(dataset, fitted, n_splits=args.oof_splits)
        print(f"\nDerived soft-voting weights: {weights}")

    print("\nBuilding soft-voting ensemble...")
    soft = fit_soft_voting(dataset, fitted, weights=weights, model_version=args.version)
    soft_path = save_ensemble(
        soft, cfg.paths.data_models / f"ensemble_soft_{args.version}.joblib"
    )

    print("Building stacking ensemble (grouped OOF -> LogisticRegression -> refit)...")
    stack = fit_stacking(
        dataset, fitted, n_oof_splits=args.oof_splits, model_version=args.version
    )
    stack_path = save_ensemble(
        stack, cfg.paths.data_models / f"ensemble_stack_{args.version}.joblib"
    )

    print(f"\nSoft-voting weights:  {soft.weights}")
    print(f"Stacking meta coefs:  {stack.meta_coefficients}")

    latency = benchmark_latency(
        {"soft_voting": soft, "stacking": stack, **{n: fitted[n].estimator for n in BASE_MODEL_NAMES}},
        dataset.X,
    )

    write_json(
        {
            "version": args.version,
            "artifacts": {"soft_voting": str(soft_path), "stacking": str(stack_path)},
            "dataset": dataset.summary(),
            "base_model_params": {n: fitted[n].params for n in BASE_MODEL_NAMES},
            "soft_voting_weights": soft.weights,
            "stacking_meta_coefficients": stack.meta_coefficients,
            "soft_voting_metadata": soft.metadata.to_dict(),
            "stacking_metadata": stack.metadata.to_dict(),
            "inference_latency_ms": latency,
            "note": (
                "Artifact-build record only. Performance numbers come from the "
                "nested LOSO run in scripts/train_all_models.py."
            ),
        },
        cfg.paths.reports / f"metrics_ensemble_artifacts_{args.version}.json",
    )
    print(f"\nArtifacts:\n  {soft_path}\n  {stack_path}")


if __name__ == "__main__":
    main()
