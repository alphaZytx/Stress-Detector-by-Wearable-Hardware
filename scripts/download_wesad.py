"""Download the WESAD dataset from Kaggle using kagglehub.

Usage:
    python3 scripts/download_wesad.py

Fallback (if Kaggle auth fails):
    1. Download manually from https://archive.ics.uci.edu/dataset/465/wesad
       (or from https://www.kaggle.com/datasets/orvile/wesad-wearable-stress-affect-detection-dataset)
    2. Extract so that per-subject folders exist at:
         data/wesad/raw/S2/S2.pkl
         data/wesad/raw/S3/S3.pkl
         ... and so on for each subject
    3. This script and the rest of the pipeline will work regardless of which
       source was used.

Kaggle auth setup (if not already configured):
    - Install: pip install kagglehub
    - Create ~/.kaggle/kaggle.json with your API credentials from
      https://www.kaggle.com/settings → API → Create New Token
"""

import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent
_WESAD_RAW = _REPO_ROOT / "data" / "wesad" / "raw"
_KAGGLE_DATASET = "orvile/wesad-wearable-stress-affect-detection-dataset"
_SUBJECTS = [
    "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9",
    "S10", "S11", "S13", "S14", "S15", "S16", "S17",
]


def _all_files_present() -> bool:
    """Return True if all subject PKL files already exist."""
    return all((_WESAD_RAW / s / f"{s}.pkl").exists() for s in _SUBJECTS)


def _find_pkl_files(download_root: Path) -> dict[str, Path]:
    """Recursively find WESAD pickle files in a downloaded directory tree."""
    found: dict[str, Path] = {}
    for pkl in download_root.rglob("*.pkl"):
        stem = pkl.stem  # e.g. "S2"
        if stem in _SUBJECTS:
            found[stem] = pkl
    return found


def main() -> None:
    if _all_files_present():
        size = sum(
            f.stat().st_size
            for f in _WESAD_RAW.rglob("*.pkl")
        )
        logger.info("All WESAD subject files already present. Total size: %.1f MB", size / 1e6)
        return

    logger.info("Downloading WESAD from Kaggle: %s", _KAGGLE_DATASET)
    try:
        import kagglehub
    except ImportError:
        logger.error("kagglehub not installed. Run: pip install kagglehub")
        sys.exit(1)

    try:
        download_path = Path(kagglehub.dataset_download(_KAGGLE_DATASET))
        logger.info("Downloaded to: %s", download_path)
    except Exception as exc:
        logger.error(
            "Kaggle download failed: %s\n"
            "Fallback: manually download from https://archive.ics.uci.edu/dataset/465/wesad "
            "and place per-subject folders in data/wesad/raw/",
            exc,
        )
        sys.exit(1)

    pkl_files = _find_pkl_files(download_path)
    if not pkl_files:
        logger.error(
            "No WESAD subject PKL files found under %s. "
            "Please check the downloaded archive structure.",
            download_path,
        )
        sys.exit(1)

    copied = 0
    for subject_id, src_pkl in pkl_files.items():
        dest_dir = _WESAD_RAW / subject_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_pkl = dest_dir / f"{subject_id}.pkl"
        if not dest_pkl.exists():
            shutil.copy2(src_pkl, dest_pkl)
            logger.info("Copied %s → %s", src_pkl.name, dest_pkl)
            copied += 1

    total_size = sum(f.stat().st_size for f in _WESAD_RAW.rglob("*.pkl"))
    logger.info(
        "Done. Copied %d file(s). Total WESAD raw size: %.1f MB",
        copied,
        total_size / 1e6,
    )

    missing = [s for s in _SUBJECTS if not (_WESAD_RAW / s / f"{s}.pkl").exists()]
    if missing:
        logger.warning(
            "Still missing subject files: %s. "
            "These subjects will be skipped during processing.",
            missing,
        )


if __name__ == "__main__":
    main()
