"""Train and evaluate the Random Forest stress classifier.

Usage:
    python3 scripts/train_random_forest.py [--version v3] [--no-tune] [--skip-loso]

Outputs:
    data/models/rf_combined_<version>.joblib
    reports/metrics_rf_combined_<version>.json

See scripts/_single_model.py for what the two different searches mean.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _single_model import build_parser, main

if __name__ == "__main__":
    main(build_parser("random_forest", "rf_combined").parse_args())
