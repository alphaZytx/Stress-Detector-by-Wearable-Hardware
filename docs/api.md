# API and Wire Contracts

## Normalized sample

```json
{
  "timestamp_ms": 125000,
  "bpm": 76,
  "avg_bpm": 74,
  "gsr": 108.4,
  "temp_c": 34.27,
  "source_label": null
}
```

## WebSocket messages

```json
{ "type": "sample", "data": {} }
{ "type": "features", "data": {}, "timestamp_ms": 125000 }
{ "type": "prediction", "data": {} }
```

The feature payload has 18 ordered values:

1. `hr_mean`
2. `hr_std`
3. `hr_min`
4. `hr_max`
5. `hr_range`
6. `hr_slope`
7. `hr_pnn_proxy`
8. `gsr_mean`
9. `gsr_std`
10. `gsr_min`
11. `gsr_max`
12. `gsr_range`
13. `gsr_slope`
14. `gsr_auc`
15. `gsr_peaks`
16. `temp_mean`
17. `temp_std`
18. `temp_slope`

The canonical list is `service/features/schema.py`. Prediction payloads include the raw and smoothed baseline/stress probabilities, timestamp, calibration flag, model type, and optional ensemble base probabilities.

REST routes provide authentication, session start/stop/list/export/delete, calibration read/write/clear, service status, and the public canned demo. Protected routes require the bearer token returned by login or registration.
