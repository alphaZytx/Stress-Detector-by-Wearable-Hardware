"""One-command reproduction of the whole multi-model pipeline.

Usage:
    python3 scripts/train_all_models.py --dataset wesad --version v2

Does, in order:
    1. verify the required feature data exists
    2. load either the WESAD-only hardware dataset or the legacy combined data
    3. tune and fit the four base models (subject-grouped GroupKFold)
    4. build the soft-voting and leakage-safe stacking artifacts
    5. benchmark single-window inference latency
    6. run the nested LOSO comparison of all seven candidates
    7. write artifacts, metrics, comparison tables, figures and the report

Nothing here downloads or synthesises data. If the feature parquet files are
missing it prints the commands that build them and exits non-zero.

Artifacts are written under new version tags; the existing v1/v2 SVM artifacts
are never overwritten.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from evaluate_models import evaluation_payload, print_summary  # noqa: E402

from stress_detection.config import get_config  # noqa: E402
from stress_detection.eval.ensemble_report import ReportInputs, generate_reports  # noqa: E402
from stress_detection.models.common import BASE_MODEL_NAMES  # noqa: E402
from stress_detection.models.dataset import (  # noqa: E402
    load_combined_dataset,
    load_wesad_dataset,
    missing_feature_data,
    missing_wesad_feature_data,
)
from stress_detection.models.evaluation import run_loso_evaluation  # noqa: E402
from stress_detection.models.training import (  # noqa: E402
    benchmark_latency,
    derive_soft_voting_weights,
    fit_all_base_models,
    fit_soft_voting,
    fit_stacking,
    save_ensemble,
    save_single_model,
    write_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# name -> artifact filename stem (§11 naming convention, continuing v1/v2).
ARTIFACT_STEMS = {
    "svm": "svm_combined",
    "random_forest": "rf_combined",
    "xgboost": "xgb_combined",
    "mlp": "mlp_combined",
}

_BUILD_HELP = """
Required feature data is missing. Build it from the datasets the repository
already supports:

  Project subject:
    python3 scripts/build_interim.py
    python3 scripts/build_features.py

  WESAD (15 subjects):
    python3 scripts/download_wesad.py
    python3 scripts/build_wesad_interim.py
    python3 scripts/build_wesad_features.py
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train and evaluate every model and ensemble.")
    parser.add_argument("--version", default="v3", help="Artifact/report version tag (default: v3).")
    parser.add_argument(
        "--dataset",
        choices=("wesad", "combined"),
        default="combined",
        help="Training data contract: WESAD-only hardware models or legacy combined data.",
    )
    parser.add_argument(
        "--no-tune", action="store_true",
        help="Use module default hyperparameters for the deployed artifacts.",
    )
    parser.add_argument(
        "--skip-loso", action="store_true",
        help="Build artifacts only; skip the nested LOSO comparison and report.",
    )
    parser.add_argument(
        "--full-grid", action="store_true",
        help="Use the full hyperparameter grids inside each outer LOSO fold (slow).",
    )
    parser.add_argument(
        "--inner-splits", type=int, default=5,
        help="Grouped folds for OOF meta-feature generation (default: 5).",
    )
    parser.add_argument(
        "--tune-splits", type=int, default=3,
        help="Grouped folds for in-fold hyperparameter search (default: 3).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cfg = get_config()
    version = args.version

    # 1. verify the feature data exists ------------------------------------
    wesad_only = args.dataset == "wesad"
    missing = missing_wesad_feature_data() if wesad_only else missing_feature_data()
    if missing:
        for path in missing:
            logger.error("Missing: %s", path)
        print(_BUILD_HELP)
        sys.exit(1)

    # 2. load the dataset ---------------------------------------------------
    dataset = load_wesad_dataset() if wesad_only else load_combined_dataset()
    artifact_stems = (
        {
            "svm": "svm_wesad_hardware",
            "random_forest": "rf_wesad_hardware",
            "xgboost": "xgb_wesad_hardware",
            "mlp": "mlp_wesad_hardware",
        }
        if wesad_only
        else ARTIFACT_STEMS
    )
    ensemble_prefix = "_wesad_hardware" if wesad_only else ""
    report_prefix = "wesad_hardware_" if wesad_only else ""
    print(f"\n{'=' * 70}")
    print(f"Dataset: {dataset.n_windows:,} windows | {dataset.n_subjects} subjects | "
          f"{len(dataset.feature_names)} features")
    print(f"  baseline={int((dataset.y == 0).sum()):,}  stress={int((dataset.y == 1).sum()):,}")
    print(f"{'=' * 70}")

    # 3. tune + fit the four base models ------------------------------------
    print("\n[1/5] Fitting base models on all subjects (GroupKFold search)...")
    fitted = fit_all_base_models(dataset, tune=not args.no_tune)
    artifacts: dict[str, str] = {}
    for name in BASE_MODEL_NAMES:
        model = fitted[name]
        score = f"{model.cv_score:.4f}" if model.cv_score is not None else "n/a"
        print(f"  {name:15s} grouped-CV f1_macro={score}  params={model.params or '(defaults)'}")
        path = save_single_model(
            model, dataset,
            cfg.paths.data_models / f"{artifact_stems[name]}_{version}.joblib",
            model_version=version,
        )
        artifacts[f"{name} base model"] = str(path.relative_to(_REPO_ROOT))

    # 4. build the ensembles -------------------------------------------------
    print("\n[2/5] Building ensembles...")
    soft = fit_soft_voting(dataset, fitted, model_version=version)
    soft_path = save_ensemble(
        soft,
        cfg.paths.data_models / f"ensemble_soft{ensemble_prefix}_{version}.joblib",
    )
    artifacts["soft-voting ensemble (equal weights)"] = str(soft_path.relative_to(_REPO_ROOT))
    print(f"  soft voting     weights={ {k: round(v, 3) for k, v in soft.weights.items()} }")

    stack = fit_stacking(dataset, fitted, n_oof_splits=args.inner_splits, model_version=version)
    stack_path = save_ensemble(
        stack,
        cfg.paths.data_models / f"ensemble_stack{ensemble_prefix}_{version}.joblib",
    )
    artifacts["stacking ensemble (LogisticRegression meta-model)"] = str(
        stack_path.relative_to(_REPO_ROOT)
    )
    print(f"  stacking        meta coefs={ {k: round(v, 3) for k, v in stack.meta_coefficients.items()} }")

    derived_weights = derive_soft_voting_weights(dataset, fitted, n_splits=args.inner_splits)
    print(f"  derived weights (experiment) = { {k: round(v, 3) for k, v in derived_weights.items()} }")

    # 5. latency benchmark ---------------------------------------------------
    print("\n[3/5] Benchmarking single-window inference latency...")
    latency = benchmark_latency(
        {
            **{name: fitted[name].estimator for name in BASE_MODEL_NAMES},
            "soft_voting": soft,
            "stacking": stack,
        },
        dataset.X,
    )
    for name, stats in latency.items():
        print(f"  {name:15s} median={stats['median_ms']:.2f} ms  p95={stats['p95_ms']:.2f} ms")

    artifact_record = {
        "version": version,
        "artifacts": artifacts,
        "dataset": dataset.summary(),
        "base_model_params": {n: fitted[n].params for n in BASE_MODEL_NAMES},
        "base_model_grouped_cv_f1_macro": {n: fitted[n].cv_score for n in BASE_MODEL_NAMES},
        "soft_voting_weights": soft.weights,
        "soft_voting_derived_weights_experiment": derived_weights,
        "stacking_meta_coefficients": stack.meta_coefficients,
        "soft_voting_metadata": soft.metadata.to_dict(),
        "stacking_metadata": stack.metadata.to_dict(),
        "inference_latency_ms": latency,
    }
    write_json(
        artifact_record,
        cfg.paths.reports / f"metrics_{report_prefix}ensemble_artifacts_{version}.json",
    )

    if args.skip_loso:
        print("\nSkipping the nested LOSO comparison (--skip-loso). Artifacts written.")
        return

    # 6. nested LOSO comparison ---------------------------------------------
    print(f"\n[4/5] Nested LOSO comparison over {dataset.n_subjects} subjects...")
    print("      (each fold re-tunes, re-generates OOF, and refits - this takes a while)")
    result = run_loso_evaluation(
        dataset.X, dataset.y, dataset.groups,
        inner_splits=args.inner_splits,
        tune_splits=args.tune_splits,
        compact_grid=not args.full_grid,
    )

    metrics_path = cfg.paths.reports / f"metrics_{report_prefix}ensemble_{version}.json"
    write_json(evaluation_payload(result, dataset, version), metrics_path)

    # 7. tables, figures, report --------------------------------------------
    print("\n[5/5] Writing tables, figures and reports/ensemble_report.md...")
    written = generate_reports(
        ReportInputs(
            result=result,
            dataset=dataset,
            version=version,
            artifacts=artifacts,
            latency=latency,
            deployment_params={n: fitted[n].params for n in BASE_MODEL_NAMES},
            soft_weights=derived_weights,
            meta_coefficients=stack.meta_coefficients,
            deployed_model=_deployed_model_type(),
        ),
        cfg.paths.reports,
    )

    print_summary(result)
    print(f"\nMetrics → {metrics_path}")
    for key, path in written.items():
        print(f"  {key:18s} {path.relative_to(_REPO_ROOT)}")
    print("\nDone.")


def _deployed_model_type() -> str | None:
    """What config/service.yaml is set to serve, so the report can say so."""
    try:
        from stress_detection.service.config import get_service_config
        from stress_detection.service.inference.loader import normalise_model_type

        return normalise_model_type(get_service_config().inference.model_type)
    except Exception:  # noqa: BLE001 - the report must not fail over this
        logger.warning("Could not read inference.model_type from the service config.")
        return None


if __name__ == "__main__":
    main()
