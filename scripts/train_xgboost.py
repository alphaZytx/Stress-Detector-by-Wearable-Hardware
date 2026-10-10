"""Train and evaluate the XGBoost stress classifier.

Usage:
    python3 scripts/train_xgboost.py [--version v3] [--no-tune] [--skip-loso]

Requires the optional xgboost dependency (`pip install -e .` picks it up; on
macOS also `brew install libomp`).

Outputs:
    data/models/xgb_combined_<version>.joblib
    reports/metrics_xgb_combined_<version>.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _single_model import build_parser, main

if __name__ == "__main__":
    main(build_parser("xgboost", "xgb_combined").parse_args())
