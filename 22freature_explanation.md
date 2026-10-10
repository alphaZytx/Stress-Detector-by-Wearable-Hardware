# Explanation of the 18 Features

The filename is retained only to avoid breaking old links. The current three-sensor system extracts **18** values from every 30-second window.

## MAX30105 heart rate — 7 features

| Feature | Meaning |
|---|---|
| `hr_mean` | Average valid BPM. |
| `hr_std` | BPM variability within the window. |
| `hr_min` | Lowest valid BPM. |
| `hr_max` | Highest valid BPM. |
| `hr_range` | Maximum minus minimum BPM. |
| `hr_slope` | Heart-rate trend across the window. |
| `hr_pnn_proxy` | Fraction of consecutive BPM readings differing by more than 5 BPM. |

## GSR skin conductance — 8 features

| Feature | Meaning |
|---|---|
| `gsr_mean` | Average conductance level. |
| `gsr_std` | Conductance variability. |
| `gsr_min` | Minimum conductance. |
| `gsr_max` | Maximum conductance. |
| `gsr_range` | Maximum minus minimum conductance. |
| `gsr_slope` | Conductance trend. |
| `gsr_auc` | Area under the conductance curve. |
| `gsr_peaks` | Count of normalized skin-conductance responses. |

## MLX90614 temperature — 3 features

| Feature | Meaning |
|---|---|
| `temp_mean` | Average temperature in °C. |
| `temp_std` | Temperature variability. |
| `temp_slope` | Warming or cooling trend. |

The canonical order is defined in `src/stress_detection/service/features/schema.py`.
