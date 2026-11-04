"""Train and honestly evaluate the calibration-aware deployment model.

The protocol mirrors live use: each subject contributes a 120-second labelled
resting calibration, those setup windows are excluded, and all remaining
windows are evaluated with nested leave-one-subject-out validation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, GroupKFold, LeaveOneGroupOut

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.models.dataset import load_personalized_wesad_dataset
from stress_detection.models.ensemble import EnsembleMetadata, library_versions
from stress_detection.models.personalized import (
    PERSONALIZED_PARAM_GRID,
    PersonalizedStressModel,
    build_personalized_extra_trees,
)
from stress_detection.service.features.schema import FEATURE_COLUMNS
from stress_detection.service.inference.loader import detect_model_type, validate_model_schema


def _metrics(y: np.ndarray, probability: np.ndarray) -> dict:
    predicted = probability >= 0.5
    return {
        "accuracy": float(accuracy_score(y, predicted)),
        "macro_f1": float(f1_score(y, predicted, average="macro")),
        "stress_f1": float(f1_score(y, predicted, pos_label=1)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
        "n_windows": int(len(y)),
    }


def nested_loso(dataset) -> tuple[dict, pd.DataFrame, list[dict]]:
    """Tune only on training subjects, then predict each held-out subject."""
    rows: list[pd.DataFrame] = []
    selections: list[dict] = []
    outer = LeaveOneGroupOut()
    started = time.perf_counter()

    for fold, (train_idx, test_idx) in enumerate(
        outer.split(dataset.X, dataset.y, dataset.groups), start=1
    ):
        subject = str(np.unique(dataset.groups[test_idx])[0])
        search = GridSearchCV(
            build_personalized_extra_trees(n_estimators=250),
            PERSONALIZED_PARAM_GRID,
            cv=GroupKFold(n_splits=4),
            scoring="f1_macro",
            n_jobs=-1,
            refit=True,
        )
        search.fit(
            dataset.X[train_idx], dataset.y[train_idx],
            groups=dataset.groups[train_idx],
        )
        probability = search.best_estimator_.predict_proba(dataset.X[test_idx])[:, 1]
        fold_metrics = _metrics(dataset.y[test_idx], probability)
        selections.append({
            "subject_id": subject,
            "best_params": search.best_params_,
            "inner_grouped_cv_macro_f1": float(search.best_score_),
            **fold_metrics,
        })
        rows.append(pd.DataFrame({
            "subject_id": dataset.groups[test_idx],
            "y_true": dataset.y[test_idx],
            "p_stress": probability,
            "prediction": (probability >= 0.5).astype(int),
        }))
        print(
            f"  {fold:02d}/{dataset.n_subjects} {subject}: "
            f"accuracy={fold_metrics['accuracy']:.3f} "
            f"macro_f1={fold_metrics['macro_f1']:.3f} "
            f"params={search.best_params_}",
            flush=True,
        )

    holdout = pd.concat(rows, ignore_index=True)
    aggregate = _metrics(
        holdout["y_true"].to_numpy(), holdout["p_stress"].to_numpy()
    )
    aggregate["evaluation"] = "nested_leave_one_subject_out"
    aggregate["n_subjects"] = dataset.n_subjects
    aggregate["calibration_seconds"] = 120
    aggregate["threshold"] = 0.5
    aggregate["fit_seconds"] = time.perf_counter() - started
    return aggregate, holdout, selections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v3")
    parser.add_argument(
        "--fallback-model",
        type=Path,
        default=Path("data/models/ensemble_soft_wesad_hardware_v2.joblib"),
    )
    args = parser.parse_args()

    dataset = load_personalized_wesad_dataset(calibration_seconds=120)
    print(
        f"Personalized dataset: {dataset.n_windows:,} windows, "
        f"{dataset.n_subjects} subjects, {dataset.X.shape[1]} features"
    )
    aggregate, holdout, folds = nested_loso(dataset)
    print("Nested LOSO:", json.dumps(aggregate, indent=2))

    print("Fitting deployable Extra Trees model on all subjects...")
    final_search = GridSearchCV(
        build_personalized_extra_trees(),
        PERSONALIZED_PARAM_GRID,
        cv=GroupKFold(n_splits=5),
        scoring="f1_macro",
        n_jobs=-1,
        refit=True,
    )
    final_search.fit(dataset.X, dataset.y, groups=dataset.groups)

    fallback_path = args.fallback_model
    if not fallback_path.is_absolute():
        fallback_path = _REPO_ROOT / fallback_path
    fallback_model = joblib.load(fallback_path)
    validate_model_schema(fallback_model, FEATURE_COLUMNS, label=fallback_path.name)
    fallback_type = detect_model_type(fallback_model)

    metadata = EnsembleMetadata(
        model_type="personalized_extra_trees",
        model_version=args.version,
        feature_names=list(FEATURE_COLUMNS),
        base_model_names=["extra_trees", fallback_type],
        base_model_params={
            "extra_trees": final_search.best_params_,
            "fallback_artifact": {"path": str(fallback_path.relative_to(_REPO_ROOT))},
        },
        threshold=0.5,
        dataset=dataset.description,
        n_subjects=dataset.n_subjects,
        n_windows=dataset.n_windows,
        trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        library_versions=library_versions(),
        evaluation=aggregate,
        requires_calibration=True,
        calibration_seconds=120,
        calibration_transform="relative_hr_gsr_and_temperature_delta_v1",
    )
    bundle = PersonalizedStressModel(
        final_search.best_estimator_, fallback_model,
        feature_names=list(FEATURE_COLUMNS),
        fallback_model_type=fallback_type,
        metadata=metadata,
    )
    validate_model_schema(bundle, FEATURE_COLUMNS)

    model_path = (
        _REPO_ROOT / "data" / "models" /
        f"personalized_extra_trees_wesad_{args.version}.joblib"
    )
    joblib.dump(bundle, model_path)

    reports = _REPO_ROOT / "reports"
    holdout.to_csv(
        reports / f"personalized_extra_trees_holdout_{args.version}.csv", index=False
    )
    pd.DataFrame(folds).to_json(
        reports / f"personalized_extra_trees_folds_{args.version}.json",
        orient="records", indent=2,
    )
    pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": final_search.best_estimator_.feature_importances_,
    }).sort_values("importance", ascending=False).to_csv(
        reports / f"personalized_extra_trees_importance_{args.version}.csv", index=False
    )
    with open(reports / f"metrics_personalized_extra_trees_{args.version}.json", "w") as f:
        json.dump({
            "version": args.version,
            "dataset": dataset.summary(),
            "nested_loso": aggregate,
            "final_grouped_cv_macro_f1": float(final_search.best_score_),
            "final_params": final_search.best_params_,
            "artifact": str(model_path.relative_to(_REPO_ROOT)),
            "fallback_model_type": fallback_type,
        }, f, indent=2)

    print(f"Final params: {final_search.best_params_}")
    print(f"Saved model: {model_path}")


if __name__ == "__main__":
    main()
