# Hardware Serial Format

The ESP32 emits one UTF-8 CSV line per second at 115200 baud:

```text
timestamp,bpm,avg_bpm,gsr,temp_c
```

| Position | Field | Type | Source | Rule |
|---:|---|---|---|---|
| 1 | `timestamp` | integer | ESP32 | Device time in milliseconds; the serial adapter uses its own fixed 1 Hz stream clock for window alignment. |
| 2 | `bpm` | number | MAX30105 | Current heart rate. Values outside 40–200, including zero before lock, become `null`. |
| 3 | `avg_bpm` | number | MAX30105 | Firmware-smoothed heart rate; same validity limits. |
| 4 | `gsr` | number | GSR sensor | Raw ADC or calibrated conductance value. Keep one unit convention within a recording. |
| 5 | `temp_c` | number | MLX90614 | Object/skin temperature in degrees Celsius. |

Example packet:

```text
125000,76,74,108.4,34.27
```

An optional nonnumeric prefix such as `DATA,` is accepted. Empty, header, partial, or malformed lines are skipped and logged. Additional fields are ignored, but new firmware should emit only the five defined fields.

For TCP input, send the equivalent newline-delimited JSON object using `timestamp_ms` instead of `timestamp`.
