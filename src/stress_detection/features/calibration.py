"""Shared personal-baseline transform used by training and live inference.

The personalized model is trained on relative physiology rather than absolute
sensor units.  This is important for GSR in particular: WESAD reports EDA in
microsiemens while the project hardware reports an ADC-scale value.  Dividing
the magnitude features by a user's resting value removes a positive linear
scale factor; temperature is expressed as a delta because Celsius already has
a meaningful common scale.
"""

from __future__ import annotations

from collections.abc import Mapping

_EPSILON = 1e-9

HR_RELATIVE_FEATURES = (
    "hr_mean", "hr_std", "hr_min", "hr_max", "hr_range", "hr_slope",
)
GSR_RELATIVE_FEATURES = (
    "gsr_mean", "gsr_std", "gsr_min", "gsr_max", "gsr_range", "gsr_slope",
    "gsr_auc",
)


def has_complete_baseline(
    hr_baseline: float | None,
    gsr_baseline: float | None,
    temp_baseline: float | None,
) -> bool:
    """Whether all values required by the personalized model are usable."""
    return (
        hr_baseline is not None
        and gsr_baseline is not None
        and temp_baseline is not None
        and abs(float(hr_baseline)) > _EPSILON
        and abs(float(gsr_baseline)) > _EPSILON
    )


def apply_relative_baseline(
    features: Mapping[str, float],
    *,
    hr_baseline: float,
    gsr_baseline: float,
    temp_baseline: float,
) -> dict[str, float]:
    """Return the exact relative feature representation used for training.

    Heart-rate and GSR magnitude features are divided by their resting means;
    skin temperature becomes a deviation from its resting mean. Unitless peak
    and pNN proxies, standard temperature variation, and slopes in Celsius are
    left unchanged.
    """
    if not has_complete_baseline(hr_baseline, gsr_baseline, temp_baseline):
        raise ValueError("A non-zero HR/GSR and a temperature baseline are required.")

    adjusted = {key: float(value) for key, value in features.items()}
    hr = float(hr_baseline)
    gsr = float(gsr_baseline)
    for key in HR_RELATIVE_FEATURES:
        if key in adjusted:
            adjusted[key] /= hr
    for key in GSR_RELATIVE_FEATURES:
        if key in adjusted:
            adjusted[key] /= gsr
    if "temp_mean" in adjusted:
        adjusted["temp_mean"] -= float(temp_baseline)
    return adjusted
