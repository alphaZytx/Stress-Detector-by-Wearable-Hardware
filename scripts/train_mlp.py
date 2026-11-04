"""Train and evaluate the MLP stress classifier (18 -> 64 -> 32 -> 16 -> 2).

Usage:
    python3 scripts/train_mlp.py [--version v3] [--no-tune] [--skip-loso]

Outputs:
    data/models/mlp_combined_<version>.joblib
    reports/metrics_mlp_combined_<version>.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _single_model import build_parser, main

if __name__ == "__main__":
    main(build_parser("mlp", "mlp_combined").parse_args())
