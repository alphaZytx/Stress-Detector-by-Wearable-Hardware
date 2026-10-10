"""Run the nested LOSO comparison and write every table, figure and the report.

Usage:
    python3 scripts/evaluate_models.py [--version v3] [--full-grid]

Outputs (under reports/):
    ensemble_report.md
    ensemble_comparison_<version>.csv
    ensemble_fold_metrics_<version>.csv
    ensemble_probability_correlation_<version>.csv
    ensemble_probability_distribution_<version>.csv
    metrics_ensemble_<version>.json
    ensemble/*.png

This is the evaluation half of ``scripts/train_all_models.py``; run it on its
own to regenerate the comparison without refitting the deployable artifacts.
Artifact-specific sections of the report (deployed hyperparameters, latency)
are filled from ``reports/metrics_ensemble_artifacts_<version>.json`` when that
file exists, and left out otherwise.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config  # noqa: E402
from stress_detection.eval.ensemble_report import ReportInputs, generate_reports  # noqa: E402
from stress_detection.models.dataset import load_combined_dataset, missing_feature_data  # noqa: E402
from stress_detection.models.evaluation import (  # noqa: E402
    loso_result_from_holdout,
    run_loso_evaluation,
)
from stress_detection.models.training import write_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nested LOSO comparison of all models.")
    parser.add_argument("--version", default="v3", help="Version tag (default: v3).")
    parser.add_argument(
        "--full-grid", action="store_true",
        help="Use the full hyperparameter grids inside each outer fold "
             "(much slower; the compact grids are the default).",
    )
    parser.add_argument(
        "--inner-splits", type=int, default=5,
        help="Grouped folds used for OOF meta-feature generation (default: 5).",
    )
    parser.add_argument(
        "--tune-splits", type=int, default=3,
        help="Grouped folds used for in-fold hyperparameter search (default: 3).",
    )
    parser.add_argument(
        "--from-cache", action="store_true",
        help="Rebuild the tables, figures and report from the held-out "
             "probabilities of a previous run instead of re-running the sweep. "
             "Every metric is recomputed from those probabilities, so the "
             "output cannot drift from the run that produced them.",
    )
    return parser


def evaluation_payload(result, dataset, version: str) -> dict:
    """The machine-readable metrics record for reports/metrics_ensemble_*.json."""
    return {
        "version": version,
        "protocol": (
            "nested leave-one-subject-out; hyperparameters, OOF generation, "
            "meta-model training and soft-voting weights all confined to the "
            "training subjects of each outer fold"
        ),
        "dataset": dataset.summary(),
        "candidates": list(result.candidates),
        "subjects": list(result.subjects),
        "aggregate": {c: result.aggregate(c) for c in result.candidates},
        "fold_metrics": {c: result.fold_metrics[c] for c in result.candidates},
        "probability_correlation": result.probability_correlation(),
        "per_fold_tuned_params": result.tuned_params,
        "per_fold_soft_weights": result.soft_weights,
        "per_fold_meta_coefficients": result.meta_coefficients,
        "evaluation_seconds": result.fit_seconds,
    }


def main() -> None:
    args = build_parser().parse_args()
    cfg = get_config()

    missing = missing_feature_data()
    if missing:
        logger.error("Missing feature data: %s", ", ".join(str(p) for p in missing))
        logger.error("Build it first - see scripts/build_features.py and scripts/build_wesad_features.py.")
        sys.exit(1)

    dataset = load_combined_dataset()
    print(
        f"\nDataset: {dataset.n_windows:,} windows, {dataset.n_subjects} subjects, "
        f"{len(dataset.feature_names)} features\n"
    )

    metrics_path = cfg.paths.reports / f"metrics_ensemble_{args.version}.json"

    if args.from_cache:
        result = _result_from_cache(cfg.paths.reports, args.version)
        print("Rebuilt from cached held-out probabilities - no sweep re-run.\n")
    else:
        result = run_loso_evaluation(
            dataset.X, dataset.y, dataset.groups,
            inner_splits=args.inner_splits,
            tune_splits=args.tune_splits,
            compact_grid=not args.full_grid,
        )
        write_json(evaluation_payload(result, dataset, args.version), metrics_path)

    artifacts_record = _load_artifact_record(cfg.paths.reports, args.version)
    written = generate_reports(
        ReportInputs(
            result=result,
            dataset=dataset,
            version=args.version,
            artifacts=artifacts_record.get("artifacts", {}),
            latency=artifacts_record.get("inference_latency_ms", {}),
            deployment_params=artifacts_record.get("base_model_params", {}),
            soft_weights=artifacts_record.get("soft_voting_weights"),
            meta_coefficients=artifacts_record.get("stacking_meta_coefficients"),
            deployed_model=_deployed_model_type(),
        ),
        cfg.paths.reports,
    )

    print_summary(result)
    if not args.from_cache:
        print(f"\nMetrics → {metrics_path}")
    for key, path in written.items():
        print(f"  {key:18s} {path}")


def _result_from_cache(reports_dir: Path, version: str):
    """Rebuild a LosoResult from a previous run's held-out probability table."""
    import pandas as pd

    holdout_path = reports_dir / f"ensemble_holdout_probabilities_{version}.csv"
    if not holdout_path.exists():
        logger.error(
            "No cached probabilities at %s. Run without --from-cache first.",
            holdout_path,
        )
        sys.exit(1)

    metrics_path = reports_dir / f"metrics_ensemble_{version}.json"
    cached: dict = {}
    if metrics_path.exists():
        with open(metrics_path) as handle:
            cached = json.load(handle)

    return loso_result_from_holdout(
        pd.read_csv(holdout_path),
        tuned_params=cached.get("per_fold_tuned_params"),
        soft_weights=cached.get("per_fold_soft_weights"),
        meta_coefficients=cached.get("per_fold_meta_coefficients"),
        fit_seconds=cached.get("evaluation_seconds", 0.0),
    )


def _load_artifact_record(reports_dir: Path, version: str) -> dict:
    path = reports_dir / f"metrics_ensemble_artifacts_{version}.json"
    if not path.exists():
        logger.info("No artifact record at %s - report will omit deployed-model detail.", path)
        return {}
    with open(path) as handle:
        return json.load(handle)


def print_summary(result) -> None:
    from stress_detection.eval.ensemble_reports import display_name

    print(f"\n=== Nested LOSO comparison ({len(result.subjects)} subjects) ===")
    print(f"{'Model':<26} {'Accuracy':>9} {'Macro F1':>9} {'Stress F1':>10} {'ROC-AUC':>8}")
    print("-" * 66)
    rows = sorted(
        result.candidates, key=lambda c: result.aggregate(c)["pooled_macro_f1"], reverse=True
    )
    for candidate in rows:
        agg = result.aggregate(candidate)
        auc = agg["pooled_roc_auc"]
        print(
            f"{display_name(candidate):<26} {agg['pooled_accuracy']:>9.3f} "
            f"{agg['pooled_macro_f1']:>9.3f} {agg['pooled_stress_f1']:>10.3f} "
            f"{(f'{auc:.3f}' if auc is not None else 'n/a'):>8}"
        )


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
