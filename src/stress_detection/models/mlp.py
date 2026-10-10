"""Small MLP base model: StandardScaler -> 22 -> 64 -> 32 -> 16 -> 2.

Scaling is mandatory here, not optional as it is for the forest. The 22
features span raw-ADC GSR (~10^2), BPM (~10^1) and per-sample slopes (~10^-2);
an unscaled network would spend its first epochs undoing that spread. The same
``StandardScaler`` step the SVM baseline uses is reused, so the two models see
identically transformed inputs.

``early_stopping=True`` carves its 10% validation slice out of whatever it is
handed, which inside a LOSO fold is the training subjects only - the held-out
subject is never part of it.

Hyperparameter search space (justification): the architecture is fixed at the
brief's 64/32/16 and only the two knobs that actually move at this sample size
are searched - L2 strength (``alpha``) and initial step size
(``learning_rate_init``). Widening the architecture search on ~5.5k windows and
18 features mostly buys variance, and every extra candidate is multiplied by 16
outer folds in the nested evaluation.
"""

from __future__ import annotations

from typing import Any

from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .common import RANDOM_SEED

_DEFAULTS: dict[str, Any] = {
    "hidden_layer_sizes": (64, 32, 16),
    "activation": "relu",
    "solver": "adam",
    "alpha": 1e-4,
    "learning_rate_init": 1e-3,
    "max_iter": 500,
    "early_stopping": True,
    "n_iter_no_change": 15,
    "validation_fraction": 0.1,
    "random_state": RANDOM_SEED,
}

PARAM_GRID: dict[str, list] = {
    "mlp__alpha": [1e-4, 1e-3, 1e-2],
    "mlp__learning_rate_init": [1e-3, 3e-3],
}

COMPACT_PARAM_GRID: dict[str, list] = {
    "mlp__alpha": [1e-4, 1e-3],
}


def build_mlp(**overrides: Any) -> Pipeline:
    """Return an unfitted StandardScaler -> MLPClassifier pipeline.

    Overrides are applied to the MLP step; pass either bare names
    (``alpha=1e-3``) or the pipeline-qualified form (``mlp__alpha=1e-3``).
    """
    params = dict(_DEFAULTS)
    for key, value in overrides.items():
        params[key.removeprefix("mlp__")] = value
    return Pipeline([("scaler", StandardScaler()), ("mlp", MLPClassifier(**params))])
