"""Train and evaluate the SVM baseline through the shared model interface.

The original scripts/train_combined.py is unchanged and still reproduces the
v1/v2 artifacts exactly. This script exists so the baseline can be rebuilt with
the same tuning/evaluation protocol as the added models, for a like-for-like
comparison.

Usage:
    python3 scripts/train_svm_combined.py [--version v3] [--no-tune] [--skip-loso]

Outputs:
    data/models/svm_combined_<version>.joblib   (does NOT overwrite v1/v2)
    reports/metrics_svm_combined_<version>.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _single_model import build_parser, main

if __name__ == "__main__":
    main(build_parser("svm", "svm_combined").parse_args())
