"""Train the combined SVM stress classifier (WESAD + project data).

Concatenates features_wesad_v1.parquet (15 subjects) and features_v1.parquet
(1 project subject, labeled "PROJECT"). Subject-grouped cross-validation across
all 16 subjects using LeaveOneGroupOut.

Outputs:
  data/models/svm_combined_v1.joblib
  reports/metrics_combined_v1.json
  reports/confusion_combined_v1.png
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from stress_detection.config import get_config
from stress_detection.models.svm import evaluate, tune_svm

_META_COLS = {"window_start_ms", "window_end_ms", "condition", "label", "subject_id"}


def _plot_confusion(cm: list[list[int]], save_path: Path) -> None:
    cm_arr = np.array(cm)
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm_arr, cmap="Blues")
    plt.colorbar(im, ax=ax)
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["baseline", "stress"])
    ax.set_yticklabels(["baseline", "stress"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix - Combined SVM (LOSO, 16 subjects)")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm_arr[i, j]), ha="center", va="center", fontsize=14,
                    color="white" if cm_arr[i, j] > cm_arr.max() / 2 else "black")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    logger.info("Confusion matrix saved → %s", save_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the combined SVM.")
    parser.add_argument(
        "--version", default="v1",
        help="Model version tag for output filenames (e.g. v1, v2). Default: v1.",
    )
    args = parser.parse_args()
    ver = args.version

    cfg = get_config()

    wesad_path = cfg.paths.data_features / "features_wesad_v1.parquet"
    proj_path = cfg.paths.data_features / "features_v1.parquet"

    for p in [wesad_path, proj_path]:
        if not p.exists():
            logger.error("Missing: %s", p)
            sys.exit(1)

    wesad_df = pd.read_parquet(wesad_path)
    proj_df = pd.read_parquet(proj_path)
    proj_df = proj_df.copy()
    proj_df["subject_id"] = "PROJECT"

    combined = pd.concat([wesad_df, proj_df], ignore_index=True)

    label_map = {"baseline": 0, "stress": 1}
    combined = combined[combined["label"].isin(label_map)].copy()
    combined["y"] = combined["label"].map(label_map)

    feat_cols = [c for c in combined.columns if c not in _META_COLS and c != "y"]
    X = combined[feat_cols].to_numpy(dtype=float)
    y = combined["y"].to_numpy(dtype=int)
    groups = combined["subject_id"].to_numpy()

    logger.info("Features: %d  |  Samples: %d  |  Subjects: %d",
                len(feat_cols), len(y), len(np.unique(groups)))
    logger.info("Class distribution: baseline=%d  stress=%d",
                (y == 0).sum(), (y == 1).sum())

    logger.info("Grid-searching hyperparameters with GroupKFold(5)...")
    model, cv_results = tune_svm(X, y, groups=groups)
    logger.info("Hyperparameter search complete.")

    logger.info("Evaluating with LeaveOneGroupOut (16 folds)...")
    metrics = evaluate(model, X, y, groups=groups)

    print("\n=== Combined SVM Results (LOSO, 16 subjects) ===")
    print(f"Accuracy:    {metrics['accuracy_mean']:.3f} ± {metrics['accuracy_std']:.3f}")
    print(f"Macro F1:    {metrics['macro_f1_mean']:.3f} ± {metrics['macro_f1_std']:.3f}")
    print(f"Weighted F1: {metrics['weighted_f1_mean']:.3f}")
    print(f"Folds:       {metrics['n_folds']}")
    print(f"Per-class F1 [baseline, stress]: {[f'{v:.3f}' for v in metrics['f1_per_class']]}")

    if metrics["macro_f1_mean"] < 0.6:
        logger.warning(
            "LOSO macro F1 = %.3f < 0.60 - below expected range.",
            metrics["macro_f1_mean"],
        )

    cfg.paths.data_models.mkdir(parents=True, exist_ok=True)
    cfg.paths.reports.mkdir(parents=True, exist_ok=True)

    best_params = model.named_steps["svc"].get_params()
    logger.info("Fitted SVC params: C=%s gamma=%s kernel=%s",
                best_params["C"], best_params["gamma"], best_params["kernel"])

    model_path = cfg.paths.data_models / f"svm_combined_{ver}.joblib"
    joblib.dump(model, model_path)
    logger.info("Model saved → %s", model_path)

    metrics_out = {
        "dataset": "WESAD+project",
        "n_subjects": int(len(np.unique(groups))),
        "n_windows": int(len(y)),
        "n_features": len(feat_cols),
        "feature_names": feat_cols,
        "best_params": {"C": best_params["C"], "gamma": best_params["gamma"],
                        "kernel": best_params["kernel"]},
        **{k: v for k, v in metrics.items()},
    }
    metrics_path = cfg.paths.reports / f"metrics_combined_{ver}.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_out, f, indent=2)
    logger.info("Metrics saved → %s", metrics_path)

    cm_path = cfg.paths.reports / f"confusion_combined_{ver}.png"
    _plot_confusion(metrics["confusion_matrix"], cm_path)


if __name__ == "__main__":
    main()
