"""Build feature table from cleaned sensor parquet.

Reads:  data/interim/sensors_clean.parquet
Writes: data/features/features_v1.parquet
        reports/feature_summary_v1.csv

Prints: window counts, feature count, top discriminative features.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd

from stress_detection.config import get_config
from stress_detection.features.pipeline import build_feature_table


def _separation_score(df: pd.DataFrame, feature_cols: list[str]) -> pd.Series:
    """Absolute mean difference normalised by pooled std (Cohen's d approximation)."""
    base = df[df["condition"] == "baseline"][feature_cols]
    stress = df[df["condition"] == "stress"][feature_cols]

    mean_diff = (stress.mean() - base.mean()).abs()
    pooled_std = np.sqrt((base.std() ** 2 + stress.std() ** 2) / 2)
    score = mean_diff / pooled_std.replace(0, np.nan)
    return score.sort_values(ascending=False)


def main() -> None:
    cfg = get_config()
    cfg.paths.data_features.mkdir(parents=True, exist_ok=True)
    cfg.paths.reports.mkdir(parents=True, exist_ok=True)

    sensors_df = pd.read_parquet(cfg.paths.data_interim / "sensors_clean.parquet")

    feat_df = build_feature_table(sensors_df)

    out_feat = cfg.paths.data_features / "features_v1.parquet"
    feat_df.to_parquet(out_feat, index=False)

    meta_cols = ["window_start_ms", "window_end_ms", "condition", "label"]
    feature_cols = [c for c in feat_df.columns if c not in meta_cols]

    # per-condition summary: mean ± std for every feature
    summary_rows = []
    for cond in ["baseline", "stress"]:
        sub = feat_df[feat_df["condition"] == cond][feature_cols]
        for col in feature_cols:
            summary_rows.append({
                "condition": cond,
                "feature": col,
                "mean": sub[col].mean(),
                "std": sub[col].std(),
            })
    summary_df = pd.DataFrame(summary_rows)
    out_summary = cfg.paths.reports / "feature_summary_v1.csv"
    summary_df.to_csv(out_summary, index=False)

    # counts
    condition_counts = feat_df["condition"].value_counts()
    print(f"Total windows:   {len(feat_df)}")
    for cond, cnt in condition_counts.items():
        print(f"  {cond}: {cnt} windows")
    print(f"Feature columns: {len(feature_cols)}")
    print(f"Saved: {out_feat}")
    print(f"Saved: {out_summary}\n")

    # top discriminative features
    scores = _separation_score(feat_df, feature_cols)
    print("Top 10 stress-discriminative features (|mean diff| / pooled std):")
    print(f"{'Feature':<22} {'Score':>8}   {'Baseline mean':>14}   {'Stress mean':>12}")
    print("-" * 65)
    for feat, score in scores.head(10).items():
        b_mean = feat_df[feat_df["condition"] == "baseline"][feat].mean()
        s_mean = feat_df[feat_df["condition"] == "stress"][feat].mean()
        print(f"  {feat:<20} {score:>8.3f}   {b_mean:>14.3f}   {s_mean:>12.3f}")


if __name__ == "__main__":
    main()
