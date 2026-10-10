"""Tables and figures for the model / ensemble comparison (§18, §19).

Everything here is derived from a :class:`~stress_detection.models.evaluation.LosoResult`
- i.e. from actual held-out predictions. Nothing is hard-coded, and no figure
can show a number that the evaluation did not produce.

Design notes for the figures
----------------------------
Each chart is a static PNG on one light surface, so the palette below is the
light column only.

* **Model comparison** is one measure across categories, so it is a bar chart
  with a single hue; the SVM baseline is a stable entity distinction (baseline
  vs candidate), not a rank, so it carries the second hue and a two-entry
  legend. Every bar is direct-labelled, so identity never rests on colour.
* **Confusion matrices** and the **probability-correlation matrix** encode
  magnitude, so both use one hue light→dark - never a rainbow. Every cell is
  annotated, and the correlation matrix is pinned to a fixed [0, 1] domain so
  the colours mean the same thing between runs instead of stretching to
  whatever the data happened to span.
* **Fold-level results** are an identity comparison across 16 subjects. 16x3
  bars would be unreadable, so it is a dot plot with a connecting hairline per
  subject, using the three categorical slots that are validated for all-pairs
  separation (the case that scatter/dot forms need).

Palette values are the validated defaults (adjacent and all-pairs CVD ΔE and
normal-vision ΔE all clear their floors on this surface). The aqua slot sits
just under 3:1 contrast, which obliges visible labels - every figure here ships
direct labels and a matching CSV table beside it.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from stress_detection.models.evaluation import LosoResult  # noqa: E402

logger = logging.getLogger(__name__)

# -- palette (light surface) ------------------------------------------------
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES_1 = "#2a78d6"   # blue   - candidate models
SERIES_2 = "#eb6834"   # orange - the SVM baseline
SERIES_3 = "#1baf7a"   # aqua   - third series in the fold plot

# Single-hue sequential ramp (blue 100 → 700), for the two magnitude heatmaps.
_BLUE_STEPS = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]
BLUE_SEQUENTIAL = LinearSegmentedColormap.from_list("blue_sequential", _BLUE_STEPS)

DISPLAY_NAMES = {
    "svm": "SVM (baseline)",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "mlp": "MLP",
    "soft_voting": "Soft Voting",
    "soft_voting_weighted": "Soft Voting (weighted)",
    "stacking": "Stacking",
}


def display_name(candidate: str) -> str:
    return DISPLAY_NAMES.get(candidate, candidate)


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)
        ax.spines[spine].set_linewidth(1.0)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)


# --------------------------------------------------------------------------
# Tables (§18)
# --------------------------------------------------------------------------


def comparison_table(result: LosoResult) -> pd.DataFrame:
    """The headline comparison: one row per candidate, LOSO-pooled metrics."""
    rows = []
    for candidate in result.candidates:
        agg = result.aggregate(candidate)
        rows.append({
            "model": display_name(candidate),
            "key": candidate,
            "accuracy": agg["pooled_accuracy"],
            "macro_f1": agg["pooled_macro_f1"],
            "stress_f1": agg["pooled_stress_f1"],
            "baseline_f1": agg["pooled_baseline_f1"],
            "baseline_precision": agg["pooled_baseline_precision"],
            "baseline_recall": agg["pooled_baseline_recall"],
            "stress_precision": agg["pooled_stress_precision"],
            "stress_recall": agg["pooled_stress_recall"],
            "roc_auc": agg["pooled_roc_auc"],
            "brier": agg["pooled_brier"],
            "accuracy_fold_mean": agg["accuracy_mean"],
            "accuracy_fold_std": agg["accuracy_std"],
            "macro_f1_fold_mean": agg["macro_f1_mean"],
            "macro_f1_fold_std": agg["macro_f1_std"],
            "roc_auc_fold_mean": agg["roc_auc_mean"],
            "roc_auc_fold_std": agg["roc_auc_std"],
            "n_folds": agg["n_folds"],
        })
    return pd.DataFrame(rows)


def fold_table(result: LosoResult) -> pd.DataFrame:
    """Per-subject, per-candidate metrics - §19.4's fold-level view."""
    rows = []
    for candidate in result.candidates:
        for fold in result.fold_metrics[candidate]:
            rows.append({
                "model": display_name(candidate),
                "key": candidate,
                "subject_id": fold["subject_id"],
                "n_windows": fold["n_samples"],
                "accuracy": fold["accuracy"],
                "macro_f1": fold["macro_f1"],
                "stress_f1": fold["stress_f1"],
                "baseline_f1": fold["baseline_f1"],
                "roc_auc": fold["roc_auc"],
                "brier": fold["brier"],
            })
    return pd.DataFrame(rows)


def probability_correlation_table(result: LosoResult) -> pd.DataFrame:
    corr = result.probability_correlation()
    names = result.candidates
    return pd.DataFrame(
        [[corr[a][b] for b in names] for a in names],
        index=[display_name(n) for n in names],
        columns=[display_name(n) for n in names],
    )


def probability_distribution_table(result: LosoResult) -> pd.DataFrame:
    """Raw P(stress) distribution per candidate, split by true class (§9).

    Comparable spreads are the precondition for averaging probabilities at all;
    a model whose P(stress) never leaves [0.4, 0.6] contributes almost nothing
    to a soft vote no matter what its accuracy is.
    """
    rows = []
    for candidate in result.candidates:
        p = result.probabilities[candidate]
        for label, mask in (("baseline", result.y_true == 0), ("stress", result.y_true == 1)):
            subset = p[mask]
            rows.append({
                "model": display_name(candidate),
                "key": candidate,
                "true_class": label,
                "mean": float(subset.mean()),
                "std": float(subset.std()),
                "p05": float(np.percentile(subset, 5)),
                "median": float(np.median(subset)),
                "p95": float(np.percentile(subset, 95)),
            })
    return pd.DataFrame(rows)


def holdout_probability_table(result: LosoResult) -> pd.DataFrame:
    """Every held-out window's P(stress) from every candidate, one row each.

    This is the rawest output of the evaluation and the thing every other table
    and figure is derived from - publishing it means any number in the report
    can be re-derived without re-running the 16-fold sweep.
    """
    frame = pd.DataFrame({
        "subject_id": result.row_subject,
        "y_true": result.y_true,
    })
    for candidate in result.candidates:
        frame[f"p_stress_{candidate}"] = result.probabilities[candidate]
    return frame


def format_markdown_table(df: pd.DataFrame, columns: dict[str, str], floatfmt: str = "{:.3f}") -> str:
    """Render a DataFrame as a GitHub markdown table, ``None`` → 'n/a'."""
    headers = list(columns.values())
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for key in columns:
            value = row[key]
            if value is None or (isinstance(value, float) and np.isnan(value)):
                cells.append("n/a")
            elif isinstance(value, (int, np.integer)) and not isinstance(value, bool):
                cells.append(str(int(value)))
            elif isinstance(value, (float, np.floating)):
                cells.append(floatfmt.format(float(value)))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Figures (§19)
# --------------------------------------------------------------------------


def plot_model_comparison(result: LosoResult, path: Path, metric: str = "macro_f1") -> Path:
    """Horizontal bars of the pooled metric (§19.1).

    No error bars, deliberately. The per-subject distribution is strongly skewed
    - most subjects score ~0.95 and one (the project's own hardware) scores
    ~0.35 - so a symmetric ±1 SD whisker is the wrong summary of it: every arm
    would run past the 1.0 ceiling and, clipped, would imply every model reaches
    a perfect score. The spread belongs in the per-subject dot plot, which shows
    the actual distribution, and in the comparison CSV.
    """
    table = comparison_table(result).sort_values(metric)
    labels = table["model"].tolist()
    values = table[metric].to_numpy(dtype=float)
    colors = [SERIES_2 if key == "svm" else SERIES_1 for key in table["key"]]

    fig, ax = plt.subplots(figsize=(8.5, 4.6), facecolor=SURFACE)
    y = np.arange(len(labels))
    ax.barh(y, values, height=0.62, color=colors, zorder=3)

    # Labels inside the bar end - the bars are long enough that an outside
    # label would sit against the axis edge.
    for yi, value in zip(y, values):
        ax.text(value - 0.012, yi, f"{value:.3f}", va="center", ha="right",
                fontsize=9.5, color="#ffffff", zorder=5)

    ax.set_yticks(y, labels, fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel(f"Pooled {metric.replace('_', ' ')} (LOSO)", fontsize=9.5, color=INK_SECONDARY)
    ax.set_title(
        f"{metric.replace('_', ' ').title()} by model - leave-one-subject-out, "
        f"{len(result.subjects)} subjects",
        fontsize=11.5, color=INK_PRIMARY, pad=34, loc="left",
    )
    ax.xaxis.grid(True, color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    _style_axes(ax)

    # Legend above the plot area - inside it, it lands on top of a bar.
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=SERIES_2),
        plt.Rectangle((0, 0), 1, 1, color=SERIES_1),
    ]
    legend = ax.legend(
        handles, ["Baseline (existing SVM)", "Added model / ensemble"],
        loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2,
        frameon=False, fontsize=8.5,
    )
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.text(
        0.012, 0.015,
        "Pooled over every held-out window. Per-subject spread is in the "
        "fold-level figure - it is far larger than any gap shown here.",
        fontsize=8, color=INK_MUTED,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    logger.info("Wrote %s", path)
    return path


def plot_confusion_matrices(result: LosoResult, candidates: list[str], path: Path) -> Path:
    """Row-normalised 2x2 confusion matrices, counts annotated (§19.2)."""
    n = len(candidates)
    fig, axes = plt.subplots(1, n, figsize=(3.3 * n, 3.7), facecolor=SURFACE)
    axes = np.atleast_1d(axes)

    for ax, candidate in zip(axes, candidates):
        cm = np.array(result.aggregate(candidate)["confusion_matrix"], dtype=float)
        row_totals = cm.sum(axis=1, keepdims=True)
        shares = np.divide(cm, row_totals, out=np.zeros_like(cm), where=row_totals > 0)

        ax.imshow(shares, cmap=BLUE_SEQUENTIAL, vmin=0.0, vmax=1.0)
        ax.set_xticks([0, 1], ["baseline", "stress"], fontsize=9)
        ax.set_yticks([0, 1], ["baseline", "stress"], fontsize=9)
        ax.set_xlabel("Predicted", fontsize=9, color=INK_SECONDARY)
        ax.set_ylabel("True", fontsize=9, color=INK_SECONDARY)
        ax.set_title(display_name(candidate), fontsize=10.5, color=INK_PRIMARY, pad=9)
        for i in range(2):
            for j in range(2):
                # Ink flips on the dark end of the ramp so the label stays legible.
                color = "#ffffff" if shares[i, j] > 0.55 else INK_PRIMARY
                ax.text(j, i, f"{int(cm[i, j]):,}\n{shares[i, j] * 100:.1f}%",
                        ha="center", va="center", fontsize=10, color=color)
        ax.tick_params(colors=INK_MUTED, length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        "Confusion matrices - pooled over all LOSO folds (cells: window count, row %)",
        fontsize=11.5, color=INK_PRIMARY, y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    logger.info("Wrote %s", path)
    return path


def plot_probability_correlation(result: LosoResult, path: Path) -> Path:
    """Pearson correlation of held-out P(stress) between candidates (§19.3)."""
    names = result.candidates
    corr = result.probability_correlation()
    matrix = np.array([[corr[a][b] for b in names] for a in names])
    labels = [display_name(n) for n in names]

    fig, ax = plt.subplots(figsize=(7.6, 6.4), facecolor=SURFACE)
    # Fixed 0..1 domain: correlations here are all positive, and pinning the
    # scale keeps colours comparable between runs instead of auto-stretching.
    image = ax.imshow(matrix, cmap=BLUE_SEQUENTIAL, vmin=0.0, vmax=1.0)

    ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right", fontsize=8.5)
    ax.set_yticks(range(len(labels)), labels, fontsize=8.5)
    for i in range(len(labels)):
        for j in range(len(labels)):
            color = "#ffffff" if matrix[i, j] > 0.55 else INK_PRIMARY
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center",
                    fontsize=8.5, color=color)
    ax.tick_params(colors=INK_MUTED, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    bar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    bar.set_label("Pearson r of P(stress)", fontsize=9, color=INK_SECONDARY)
    bar.ax.tick_params(colors=INK_MUTED, labelsize=8)
    bar.outline.set_visible(False)

    ax.set_title(
        "Do the models disagree? Correlation of held-out P(stress)",
        fontsize=11.5, color=INK_PRIMARY, pad=12, loc="left",
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    logger.info("Wrote %s", path)
    return path


def plot_fold_comparison(
    result: LosoResult,
    path: Path,
    candidates: tuple[str, ...] = ("svm", "soft_voting", "stacking"),
    metric: str = "macro_f1",
) -> Path:
    """Per-subject dot plot (§19.4).

    A dot plot rather than 16x3 grouped bars: the question is whether stacking
    beats the baseline *for each subject*, and the connecting hairline answers
    that at a glance. The three colours are the slots validated for all-pairs
    separation, which is the requirement for a dot form.
    """
    colors = {c: col for c, col in zip(candidates, (SERIES_2, SERIES_3, SERIES_1))}
    per_subject = {
        candidate: {f["subject_id"]: f[metric] for f in result.fold_metrics[candidate]}
        for candidate in candidates
    }
    order = sorted(result.subjects, key=lambda s: per_subject[candidates[0]][s])

    fig, ax = plt.subplots(figsize=(8.6, 0.42 * len(order) + 2.4), facecolor=SURFACE)
    y = np.arange(len(order))

    for yi, subject in zip(y, order):
        values = [per_subject[c][subject] for c in candidates]
        ax.plot([min(values), max(values)], [yi, yi], color=AXIS, linewidth=2,
                solid_capstyle="round", zorder=2)
    for candidate in candidates:
        ax.scatter(
            [per_subject[candidate][s] for s in order], y,
            s=62, color=colors[candidate], label=display_name(candidate),
            zorder=3, edgecolors=SURFACE, linewidths=2,
        )

    ax.set_yticks(y, order, fontsize=9, color=INK_SECONDARY)
    ax.set_xlabel(f"{metric.replace('_', ' ').title()} on the held-out subject",
                  fontsize=9.5, color=INK_SECONDARY)
    ax.set_xlim(-0.02, 1.02)
    ax.set_title(
        "Per-subject LOSO results - one row per held-out subject",
        fontsize=11.5, color=INK_PRIMARY, pad=34, loc="left",
    )
    ax.xaxis.grid(True, color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    _style_axes(ax)

    # Above the plot: inside, it lands on the lowest-scoring subject's row.
    legend = ax.legend(
        loc="lower left", bbox_to_anchor=(0, 1.005), ncol=len(candidates),
        frameon=False, fontsize=8.5,
    )
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    logger.info("Wrote %s", path)
    return path
