"""Build interim parquet files from raw CSVs.

Loads the recorded wearable CSVs, cleans them, and writes:
  data/interim/sensors_clean.parquet

Prints a summary table to stdout.
"""

import sys
from pathlib import Path

# allow running as a script without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from stress_detection.config import get_config
from stress_detection.io.cleaner import clean_sensors
from stress_detection.io.loader import load_sensors


def _nan_summary(df: pd.DataFrame) -> str:
    cols = [c for c in df.columns if df[c].isna().any()]
    if not cols:
        return "none"
    return ", ".join(f"{c}={df[c].isna().sum()}" for c in cols)


def main() -> None:
    cfg = get_config()
    cfg.paths.data_interim.mkdir(parents=True, exist_ok=True)

    print("=== SENSORS ===")
    sensor_parts = []
    for condition in ("baseline", "stress"):
        raw = load_sensors(condition)
        cleaned = clean_sensors(raw)
        print(
            f"  {condition}: {len(raw)} rows in → {len(cleaned)} rows out  "
            f"NaNs: {_nan_summary(cleaned)}"
        )
        sensor_parts.append(cleaned)
    sensors_df = pd.concat(sensor_parts, ignore_index=True)
    out_sensors = cfg.paths.data_interim / "sensors_clean.parquet"
    sensors_df.to_parquet(out_sensors, index=False)
    print(f"  Saved {out_sensors}  ({len(sensors_df)} total rows)\n")

    print("Done.")


if __name__ == "__main__":
    main()
