# Report Tables

## Sensor mapping

| Hardware | Signal | Live fields | Feature count |
|---|---|---|---:|
| MAX30105 | Heart rate | `bpm`, `avg_bpm` | 7 |
| GSR sensor | Skin conductance | `gsr` | 8 |
| MLX90614 | Temperature | `temp_c` | 3 |
| **Total** | | | **18** |

Regenerate current metrics and feature summaries with `scripts/build_report_artifacts.py` after retraining.
