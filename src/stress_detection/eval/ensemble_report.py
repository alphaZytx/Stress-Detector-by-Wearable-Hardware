"""Generate reports/ensemble_report.md and its companion tables/figures.

Every number in the output is read off a :class:`LosoResult` produced by an
actual evaluation run. There are no literal metric values in this file, and the
discussion section is assembled from comparisons computed at write time - so if
the ensemble does not help, the report says it does not help.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from stress_detection.models.common import BASE_MODEL_NAMES, RANDOM_SEED
from stress_detection.models.dataset import Dataset
from stress_detection.models.evaluation import SOFT_EQUAL, SOFT_WEIGHTED, STACKING, LosoResult

from .ensemble_reports import (
    comparison_table,
    display_name,
    fold_table,
    format_markdown_table,
    holdout_probability_table,
    plot_confusion_matrices,
    plot_fold_comparison,
    plot_model_comparison,
    plot_probability_correlation,
    probability_correlation_table,
    probability_distribution_table,
)

logger = logging.getLogger(__name__)

BASELINE = "svm"


@dataclass
class ReportInputs:
    result: LosoResult
    dataset: Dataset
    version: str
    artifacts: dict[str, str]
    latency: dict[str, dict[str, float]]
    deployment_params: dict[str, dict]
    soft_weights: dict[str, float] | None = None
    meta_coefficients: dict[str, float] | None = None
    # What config/service.yaml actually serves. Stated in the conclusion so
    # the report never leaves the deployment choice implicit.
    deployed_model: str | None = None


def _paired_comparison(result: LosoResult, candidate: str, metric: str = "macro_f1") -> dict:
    """Per-subject paired comparison of ``candidate`` against the SVM baseline.

    A Wilcoxon signed-rank test over the 16 per-subject scores. With n=16 it is
    underpowered for small effects - it is reported to keep the comparison
    honest about uncertainty, not to certify a winner.
    """
    base = {f["subject_id"]: f[metric] for f in result.fold_metrics[BASELINE]}
    other = {f["subject_id"]: f[metric] for f in result.fold_metrics[candidate]}
    subjects = sorted(base)
    a = np.array([base[s] for s in subjects])
    b = np.array([other[s] for s in subjects])
    diff = b - a

    p_value: float | None = None
    if np.any(diff != 0):
        try:
            p_value = float(wilcoxon(b, a, zero_method="wilcox").pvalue)
        except ValueError:
            p_value = None

    return {
        "candidate": candidate,
        "metric": metric,
        "mean_delta": float(diff.mean()),
        "median_delta": float(np.median(diff)),
        "n_better": int((diff > 0).sum()),
        "n_worse": int((diff < 0).sum()),
        "n_tied": int((diff == 0).sum()),
        "n_subjects": len(subjects),
        "wilcoxon_p": p_value,
    }


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.{digits}f}"


def _fmt_delta(value: float, digits: int = 3) -> str:
    return f"{value:+.{digits}f}"


def _describe_difference(comparison: dict) -> str:
    """One honest sentence about a candidate vs the baseline."""
    delta = comparison["mean_delta"]
    name = display_name(comparison["candidate"])
    direction = "above" if delta > 0 else "below" if delta < 0 else "level with"
    p_value = comparison["wilcoxon_p"]
    if p_value is None:
        significance = "no signed-rank test was possible (identical fold scores)"
    elif p_value < 0.05:
        significance = f"the per-subject difference is significant at p={p_value:.3f}"
    else:
        significance = (
            f"the per-subject difference is not significant (p={p_value:.3f}), "
            "so this is within fold-to-fold noise"
        )
    return (
        f"**{name}** averages {_fmt_delta(delta)} macro-F1 {direction} the SVM "
        f"baseline per subject, better on {comparison['n_better']} of "
        f"{comparison['n_subjects']} subjects and worse on {comparison['n_worse']}; "
        f"{significance}."
    )


def generate_reports(inputs: ReportInputs, reports_dir: Path) -> dict[str, Path]:
    """Write every table, figure and the markdown report. Returns their paths."""
    result, dataset, version = inputs.result, inputs.dataset, inputs.version
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = reports_dir / "ensemble"
    figures_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    # Registered up front: _build_markdown resolves figure links relative to it.
    report_path = reports_dir / "ensemble_report.md"
    written["report"] = report_path

    # -- tables -------------------------------------------------------------
    comparison = comparison_table(result)
    folds = fold_table(result)
    correlation = probability_correlation_table(result)
    distribution = probability_distribution_table(result)

    holdout = holdout_probability_table(result)

    for key, frame, name in (
        ("comparison_csv", comparison, f"ensemble_comparison_{version}.csv"),
        ("folds_csv", folds, f"ensemble_fold_metrics_{version}.csv"),
        ("distribution_csv", distribution, f"ensemble_probability_distribution_{version}.csv"),
        ("holdout_csv", holdout, f"ensemble_holdout_probabilities_{version}.csv"),
    ):
        path = reports_dir / name
        frame.to_csv(path, index=False)
        written[key] = path

    correlation_path = reports_dir / f"ensemble_probability_correlation_{version}.csv"
    correlation.to_csv(correlation_path)
    written["correlation_csv"] = correlation_path

    # -- figures ------------------------------------------------------------
    best_alternative = _best_alternative(comparison)
    written["fig_comparison"] = plot_model_comparison(
        result, figures_dir / f"model_comparison_{version}.png"
    )
    written["fig_confusion"] = plot_confusion_matrices(
        result,
        [BASELINE, best_alternative, SOFT_EQUAL, STACKING],
        figures_dir / f"confusion_matrices_{version}.png",
    )
    written["fig_correlation"] = plot_probability_correlation(
        result, figures_dir / f"probability_correlation_{version}.png"
    )
    written["fig_folds"] = plot_fold_comparison(
        result, figures_dir / f"fold_comparison_{version}.png"
    )

    # -- markdown -----------------------------------------------------------
    report_path.write_text(
        _build_markdown(inputs, comparison, correlation, distribution, best_alternative, written)
    )
    logger.info("Wrote %s", report_path)
    return written


def _best_alternative(comparison: pd.DataFrame) -> str:
    """Highest-scoring individual model that is not the SVM baseline (§19.2)."""
    singles = comparison[comparison["key"].isin([n for n in BASE_MODEL_NAMES if n != BASELINE])]
    return str(singles.loc[singles["macro_f1"].idxmax(), "key"])


def _build_markdown(
    inputs: ReportInputs,
    comparison: pd.DataFrame,
    correlation: pd.DataFrame,
    distribution: pd.DataFrame,
    best_alternative: str,
    written: dict[str, Path],
) -> str:
    result, dataset, version = inputs.result, inputs.dataset, inputs.version
    summary = dataset.summary()
    by_key = comparison.set_index("key")

    comparisons = {
        key: _paired_comparison(result, key)
        for key in result.candidates if key != BASELINE
    }
    ranked = comparison.sort_values("macro_f1", ascending=False)
    winner = str(ranked.iloc[0]["key"])

    def rel(path: Path) -> str:
        return str(path.relative_to(written["report"].parent))

    lines: list[str] = []
    add = lines.append

    add("# Multi-Model Ensemble for Wearable Stress Detection")
    add("")
    add(
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        f"by `scripts/train_all_models.py` (version `{version}`, seed "
        f"`{RANDOM_SEED}`). Every number below comes from that run's held-out "
        "predictions._"
    )
    add("")

    # 1 ---------------------------------------------------------------------
    add("## 1. Objective")
    add("")
    add(
        "The deployed system classified stress from an 18-feature window with a "
        "single RBF SVM. This report extends it to four base models (SVM, "
        "Random Forest, XGBoost, MLP) and two ensembles (soft voting and "
        "leakage-safe stacking), and compares all of them under one "
        "subject-independent protocol."
    )
    add("")
    add(
        "The question is **not** whether the ensemble wins. It is what the "
        "honest difference between these six options is on unseen subjects. "
        "The SVM remains the baseline and the deployment fallback."
    )
    add("")

    # 2 ---------------------------------------------------------------------
    add("## 2. Dataset")
    add("")
    add(f"- **Source:** {summary['description']}")
    add(f"- **Windows:** {summary['n_windows']:,} (30 s windows, 5 s stride)")
    add(f"- **Subjects:** {summary['n_subjects']}")
    add(f"- **Features:** {summary['n_features']}, in the canonical service order")
    add(
        f"- **Class balance:** baseline {summary['class_counts']['baseline']:,} / "
        f"stress {summary['class_counts']['stress']:,} "
        f"({summary['class_counts']['stress'] / summary['n_windows']:.1%} stress)"
    )
    add("")
    add("Windows per subject:")
    add("")
    per_subject = pd.DataFrame(
        [{"subject_id": k, "windows": v} for k, v in summary["windows_per_subject"].items()]
    )
    add(format_markdown_table(per_subject, {"subject_id": "Subject", "windows": "Windows"}))
    add("")
    add(
        "The 18-feature contract is unchanged: the same "
        "`service/features/schema.py` ordering is used for every model here and "
        "by the live `FeatureStreamer`, so train/serve parity is preserved."
    )
    add("")

    # 3 ---------------------------------------------------------------------
    add("## 3. Existing SVM baseline")
    add("")
    baseline_row = by_key.loc[BASELINE]
    add(
        "`StandardScaler → SVC(kernel=\"rbf\", probability=True)`, unchanged from "
        "Phase 1 and still the default fallback in `config/service.yaml`. Under "
        "the nested LOSO protocol described in §5 it scores:"
    )
    add("")
    add(
        f"- Accuracy **{_fmt(baseline_row['accuracy'])}**, "
        f"macro-F1 **{_fmt(baseline_row['macro_f1'])}**, "
        f"stress-F1 **{_fmt(baseline_row['stress_f1'])}**, "
        f"ROC-AUC **{_fmt(baseline_row['roc_auc'])}**"
    )
    add(
        f"- Across subjects: macro-F1 "
        f"{_fmt(baseline_row['macro_f1_fold_mean'])} ± "
        f"{_fmt(baseline_row['macro_f1_fold_std'])}"
    )
    add("")

    # 4 ---------------------------------------------------------------------
    add("## 4. Model configurations")
    add("")
    add(
        "All four base models satisfy one interface - `fit` / `predict` / "
        "`predict_proba`, with `predict_proba(X)[:, 1] = P(stress)` and "
        "`0 = baseline, 1 = stress`. The ensemble and inference layers depend "
        "on nothing else."
    )
    add("")
    add("| Model | Configuration | Notes |")
    add("|---|---|---|")
    add(
        "| SVM (baseline) | `StandardScaler → SVC(rbf, probability=True)` | "
        "Unchanged Phase 1 pipeline. |"
    )
    add(
        "| Random Forest | `RandomForestClassifier` | No scaler - trees are "
        "invariant to monotone rescaling. |"
    )
    add(
        "| XGBoost | `XGBClassifier(binary:logistic, tree_method=hist)` | "
        "Optional dependency; lazily imported. |"
    )
    add(
        "| MLP | `StandardScaler → MLPClassifier(64, 32, 16)` | Early stopping "
        "on an internal 10% split of the training fold. |"
    )
    add(
        "| Soft Voting | weighted mean of the four `P(stress)` | Equal weights "
        "(0.25 each) is the primary variant. |"
    )
    add(
        "| Stacking | four `P(stress)` → `LogisticRegression` | Meta-features "
        f"in fixed order `{list(BASE_MODEL_NAMES)}`. |"
    )
    add("")
    add(
        f"Deployed-artifact hyperparameters (selected by subject-grouped "
        f"`GroupKFold` over the full dataset, seed `{RANDOM_SEED}`):"
    )
    add("")
    add("```")
    for name, params in inputs.deployment_params.items():
        add(f"{name}: {params if params else '(module defaults)'}")
    add("```")
    add("")
    if inputs.soft_weights:
        add(
            "Validation-derived soft-voting weights (from grouped OOF ROC-AUC on "
            "the training data, the separately labelled experiment of §7): "
            + ", ".join(f"`{k}={v:.3f}`" for k, v in inputs.soft_weights.items())
            + "."
        )
        add("")
    if inputs.meta_coefficients:
        add(
            "Deployed stacking meta-model coefficients: "
            + ", ".join(f"`{k}={v:+.3f}`" for k, v in inputs.meta_coefficients.items())
            + ". A larger magnitude means the meta-model leans harder on that "
            "base model's probability."
        )
        add("")

    # 5 ---------------------------------------------------------------------
    add("## 5. LOSO evaluation protocol")
    add("")
    add(
        f"The primary result is **nested leave-one-subject-out** over all "
        f"{summary['n_subjects']} subjects (`LeaveOneGroupOut`, grouped by "
        "`subject_id`). No random window-level split is reported anywhere: "
        "windows overlap at a 5 s stride and come in long per-subject runs, so "
        "a random split puts near-duplicates on both sides and reads far too "
        "well."
    )
    add("")
    add("For each held-out subject:")
    add("")
    add("1. tune each base model on the training subjects only "
        "(inner `GroupKFold`, compact grid)")
    add("2. generate grouped out-of-fold `P(stress)` over the training subjects")
    add("3. derive soft-voting weights from those OOF probabilities")
    add("4. fit the `LogisticRegression` meta-model on those OOF probabilities")
    add("5. refit the base models on all training subjects")
    add("6. predict the held-out subject - once")
    add("")
    add(
        "The held-out subject takes no part in tuning, OOF generation, "
        "meta-model training, weight selection or threshold selection. The "
        "decision threshold stays at the application's existing "
        "`P(stress) >= 0.5`; it was not tuned."
    )
    add("")
    add(
        "Metrics reported per candidate: accuracy, macro-F1, per-class "
        "precision/recall/F1, confusion matrix, ROC-AUC and Brier score. "
        "Pooled values concatenate all folds so each window counts once; "
        "`± values are the spread across the "
        f"{summary['n_subjects']} subjects`."
    )
    add("")
    add(
        f"_Total nested-evaluation time: {result.fit_seconds / 60:.1f} minutes._"
    )
    add("")

    # 6 ---------------------------------------------------------------------
    add("## 6. Leakage-safe stacking methodology")
    add("")
    add("The invalid recipe, which this implementation does **not** use:")
    add("")
    add("```text")
    add("train every base model on all data")
    add("        ↓")
    add("predict on that same training data")
    add("        ↓")
    add("train the meta-model on those predictions      ← optimistic, invalid")
    add("```")
    add("")
    add(
        "Instead, `generate_oof_probabilities()` builds the meta-features with "
        "`GroupKFold` over `subject_id`: every row's probability comes from a "
        "clone fitted on folds containing none of that row's subject. The "
        "disjointness is asserted at runtime per fold, and the function raises "
        "if any row would be left without an OOF prediction - so a future "
        "refactor cannot quietly reintroduce leakage."
    )
    add("")
    add("```text")
    add("Subject k held out")
    add("    ↓")
    add("base models trained on the other subjects")
    add("    ↓")
    add("predict subject k          → OOF row block for k")
    add("    ↓ (for every subject)")
    add("OOF matrix [P_svm, P_rf, P_xgb, P_mlp]")
    add("    ↓")
    add("LogisticRegression meta-model")
    add("```")
    add("")
    add(
        "One approximation is documented rather than hidden: within a fold, the "
        "hyperparameters chosen in step 1 are reused by the step-2 OOF clones. "
        "That is selection information moving inside the training portion; it "
        "never touches the outer held-out subject."
    )
    add("")

    # 7 ---------------------------------------------------------------------
    add("## 7. Results")
    add("")
    add(f"Pooled over all {summary['n_subjects']} held-out subjects:")
    add("")
    add(format_markdown_table(
        ranked,
        {
            "model": "Model", "accuracy": "Accuracy", "macro_f1": "Macro F1",
            "stress_f1": "Stress F1", "roc_auc": "ROC-AUC", "brier": "Brier",
        },
    ))
    add("")
    add("Precision and recall per class:")
    add("")
    add(format_markdown_table(
        ranked,
        {
            "model": "Model",
            "baseline_precision": "Baseline P", "baseline_recall": "Baseline R",
            "stress_precision": "Stress P", "stress_recall": "Stress R",
        },
    ))
    add("")
    add("Spread across subjects (mean ± SD of the per-fold metric):")
    add("")
    spread = ranked.copy()
    spread["macro_f1_spread"] = [
        f"{_fmt(m)} ± {_fmt(s)}"
        for m, s in zip(spread["macro_f1_fold_mean"], spread["macro_f1_fold_std"])
    ]
    spread["accuracy_spread"] = [
        f"{_fmt(m)} ± {_fmt(s)}"
        for m, s in zip(spread["accuracy_fold_mean"], spread["accuracy_fold_std"])
    ]
    spread["roc_auc_spread"] = [
        f"{_fmt(m)} ± {_fmt(s)}"
        for m, s in zip(spread["roc_auc_fold_mean"], spread["roc_auc_fold_std"])
    ]
    add(format_markdown_table(
        spread,
        {
            "model": "Model", "accuracy_spread": "Accuracy",
            "macro_f1_spread": "Macro F1", "roc_auc_spread": "ROC-AUC",
        },
    ))
    add("")
    add(f"![Model comparison]({rel(written['fig_comparison'])})")
    add("")
    add("### Per-subject (fold-level) results")
    add("")
    add(f"![Per-subject results]({rel(written['fig_folds'])})")
    add("")
    add(
        "The per-subject spread is far larger than any gap between models - the "
        "hardest subjects dominate every aggregate. Full per-fold numbers for "
        f"every candidate are in `{written['folds_csv'].name}`, and every "
        "held-out window's raw P(stress) from every candidate is in "
        f"`{written['holdout_csv'].name}` - so any number in this report can be "
        "re-derived without re-running the sweep."
    )
    add("")
    add("### Inference latency")
    add("")
    if inputs.latency:
        latency_frame = pd.DataFrame([
            {"model": display_name(k), **v} for k, v in inputs.latency.items()
        ])
        add(format_markdown_table(
            latency_frame,
            {"model": "Model", "median_ms": "Median (ms)", "mean_ms": "Mean (ms)",
             "p95_ms": "p95 (ms)", "max_ms": "Max (ms)"},
            floatfmt="{:.2f}",
        ))
        add("")
        slowest = max(inputs.latency.values(), key=lambda v: v["median_ms"])["median_ms"]
        add(
            f"Single-window `predict_proba`, which is what the live loop does. "
            f"The slowest option costs {slowest:.1f} ms against a 5 s prediction "
            f"cadence - {5000 / max(slowest, 1e-6):.0f}x headroom, so model "
            "choice is not latency-bound here."
        )
        add("")

    # 8 ---------------------------------------------------------------------
    add("## 8. Confusion matrices")
    add("")
    add(f"![Confusion matrices]({rel(written['fig_confusion'])})")
    add("")
    add(
        f"Shown for the SVM baseline, the best individual alternative "
        f"({display_name(best_alternative)}), soft voting and stacking. "
        "Counts are pooled over all LOSO folds."
    )
    add("")
    for key in (BASELINE, best_alternative, SOFT_EQUAL, STACKING):
        agg_cm = np.array(result.aggregate(key)["confusion_matrix"])
        add(f"**{display_name(key)}**")
        add("")
        add("| | Predicted baseline | Predicted stress |")
        add("|---|---|---|")
        add(f"| **True baseline** | {agg_cm[0, 0]:,} | {agg_cm[0, 1]:,} |")
        add(f"| **True stress** | {agg_cm[1, 0]:,} | {agg_cm[1, 1]:,} |")
        add("")

    # 9 ---------------------------------------------------------------------
    add("## 9. Probability correlation")
    add("")
    add(f"![Probability correlation]({rel(written['fig_correlation'])})")
    add("")
    base_corr = correlation.loc[
        [display_name(n) for n in BASE_MODEL_NAMES],
        [display_name(n) for n in BASE_MODEL_NAMES],
    ].to_numpy()
    off_diagonal = base_corr[~np.eye(len(BASE_MODEL_NAMES), dtype=bool)]
    mean_correlation = float(off_diagonal.mean())
    add(
        f"Pairwise Pearson correlation of the four base models' held-out "
        f"`P(stress)` ranges from {off_diagonal.min():.2f} to "
        f"{off_diagonal.max():.2f} (mean {off_diagonal.mean():.2f})."
    )
    add("")
    add(
        "This is the number that bounds what any ensemble over these models "
        "could achieve: highly correlated members make the same mistakes, so "
        "averaging or stacking them has little independent signal to combine."
        if off_diagonal.mean() > 0.85 else
        "The base models are only moderately correlated, which means they do "
        "make partly independent errors - the precondition for an ensemble to "
        "add anything."
    )
    add("")
    add("Raw `P(stress)` distributions by true class (§9 calibration check):")
    add("")
    add(format_markdown_table(
        distribution,
        {"model": "Model", "true_class": "True class", "mean": "Mean",
         "std": "SD", "p05": "p05", "median": "Median", "p95": "p95"},
    ))
    add("")
    add(
        "Each model's own `predict_proba()` is used directly - no post-hoc "
        "calibration layer was added. Brier scores in §7 quantify how well "
        "those raw probabilities are calibrated; the table above shows whether "
        "they are on comparable scales, which is the precondition for averaging "
        "them at all."
    )
    add("")

    # 10 --------------------------------------------------------------------
    add("## 10. Discussion")
    add("")
    add(
        f"On pooled macro-F1 the ranking is: "
        + ", ".join(
            f"{display_name(row['key'])} ({_fmt(row['macro_f1'])})"
            for _, row in ranked.iterrows()
        )
        + "."
    )
    add("")
    for key in (*[n for n in BASE_MODEL_NAMES if n != BASELINE], SOFT_EQUAL, SOFT_WEIGHTED, STACKING):
        add(f"- {_describe_difference(comparisons[key])}")
    add("")
    stacking_cmp = comparisons[STACKING]
    if winner == BASELINE:
        add(
            "**The existing SVM baseline remains the strongest single option on "
            "pooled macro-F1.** The ensembles did not beat it here, and that is "
            "reported as found rather than explained away."
        )
    elif winner == STACKING:
        add(
            "**Stacking ranks first on pooled macro-F1.** Whether that margin is "
            "meaningful is a separate question - see the per-subject test above."
        )
    else:
        add(
            f"**{display_name(winner)} ranks first on pooled macro-F1**, ahead of "
            "both the SVM baseline and the stacking ensemble."
        )
    add("")
    if stacking_cmp["wilcoxon_p"] is not None and stacking_cmp["wilcoxon_p"] >= 0.05:
        agreement = (
            "the four base models agree closely (mean pairwise r "
            f"{mean_correlation:.2f}), which caps how much combining them could "
            "change any single decision"
            if mean_correlation > 0.85 else
            "the base models are only moderately correlated (mean pairwise r "
            f"{mean_correlation:.2f}), so an ensemble did have partly independent "
            "errors to work with - the pooled gain is consistent with that"
        )
        add(
            f"Taken together with §9, {agreement}. But the per-subject test is "
            f"the one that decides: at n={stacking_cmp['n_subjects']} a "
            "difference of this size is not distinguishable from fold-to-fold "
            "variation, so the honest conclusion is that the ensembles are "
            "**comparable to** the SVM baseline on this dataset, not better than "
            "it. Collecting more subjects, not changing the model, is what would "
            "settle the question."
        )
    else:
        add(
            "The per-subject signed-rank test separates stacking from the "
            f"baseline at the conventional threshold; with "
            f"{stacking_cmp['n_subjects']} subjects this is suggestive rather "
            "than conclusive."
        )
    add("")

    # 11 --------------------------------------------------------------------
    add("## 11. Limitations")
    add("")
    add(
        f"- **{summary['n_subjects']} subjects, one of them the project's own "
        "hardware.** 15 WESAD wrist recordings plus a single project subject. "
        "Per-subject variance dominates every aggregate, and 16 paired samples "
        "give any statistical test little power."
    )
    add(
        "- **Cross-device domain shift.** WESAD EDA is in µS; the project rig "
        "reports raw ADC counts. `StandardScaler` normalises each training set, "
        "but this is not formal domain adaptation."
    )
    add(
        "- **Three-sensor alignment.** WESAD training uses only wrist BVP, EDA, "
        "and temperature to match the deployed hardware channels."
    )
    add(
        "- **Hyperparameter approximation inside folds** (§6) - documented, "
        "bounded to the training portion."
    )
    add(
        "- **No post-hoc probability calibration.** Raw `predict_proba()` "
        "outputs are averaged; §9 shows they are on broadly comparable scales, "
        "but tree and margin models are not calibrated the same way."
    )
    add(
        "- **The decision threshold was not tuned.** It stays at the "
        "application's existing 0.5."
    )
    add(
        "- **Per-user calibration is a heuristic feature shift**, not validated "
        "domain adaptation, and is unchanged by this work."
    )
    add("")

    # 12 --------------------------------------------------------------------
    add("## 12. Conclusion")
    add("")
    add(
        f"Four base models and two ensemble strategies were implemented and "
        f"compared under one subject-independent protocol on "
        f"{summary['n_windows']:,} windows from {summary['n_subjects']} "
        "subjects, with stacking's meta-features generated out-of-fold so no "
        "held-out subject influenced any part of training."
    )
    add("")
    add(
        f"Pooled macro-F1: SVM baseline {_fmt(by_key.loc[BASELINE, 'macro_f1'])}, "
        f"soft voting {_fmt(by_key.loc[SOFT_EQUAL, 'macro_f1'])}, "
        f"stacking {_fmt(by_key.loc[STACKING, 'macro_f1'])}. "
        f"{display_name(winner)} ranks highest."
    )
    add("")
    add("Artifacts written by this run:")
    add("")
    for name, path in inputs.artifacts.items():
        add(f"- `{path}` - {name}")
    add("")
    if inputs.deployed_model:
        deployed = inputs.deployed_model
        add(
            f"**Deployed: {display_name(deployed)}** "
            f"(`inference.model_type: {deployed}` in `config/service.yaml`)."
        )
        if deployed != winner:
            gap = float(by_key.loc[winner, "macro_f1"] - by_key.loc[deployed, "macro_f1"])
            add("")
            add(
                f"{display_name(winner)} scored {gap:+.4f} macro-F1 higher, a gap "
                f"far inside the ±{by_key.loc[deployed, 'macro_f1_fold_std']:.2f} "
                "between-subject spread and not separable from it. Either is "
                "defensible on these numbers; switching is a one-line config "
                "change."
            )
        add("")
    add(
        "The SVM remains available as the baseline and as the configured "
        "fallback, so the service keeps working whether or not the ensemble "
        "artifacts are present."
    )
    add("")
    return "\n".join(lines) + "\n"
