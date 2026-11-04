# Three-Sensor Wearable Stress Detection

Real-time baseline-versus-stress classification from an ESP32 wearable using exactly three sensors:

- **MAX30105** — optical heart rate (`bpm`, `avg_bpm`)
- **GSR sensor** — skin conductance (`gsr`)
- **MLX90614** — contactless temperature (`temp_c`)

The FastAPI service accepts samples at 1 Hz, builds a rolling 30-second window, extracts 18 features every 5 seconds, runs a calibration-aware personalized Extra Trees model, smooths its probability, stores sessions in SQLite, and streams samples/features/predictions to the React dashboard. Without a complete personal baseline it automatically uses the previous Soft Voting model.

```mermaid
flowchart LR
  HR[MAX30105<br/>heart rate] --> ESP[ESP32]
  GSR[GSR sensor<br/>skin conductance] --> ESP
  TEMP[MLX90614<br/>temperature] --> ESP
  ESP -->|USB serial<br/>1 Hz CSV| API[FastAPI service]
  API --> F[30 s window<br/>18 features]
  F --> M[Classifier]
  M --> UI[React dashboard]
```

## Sensor and feature contract

The live serial packet contains five values:

```text
timestamp,bpm,avg_bpm,gsr,temp_c
```

Example:

```text
125000,76,74,108.4,34.27
```

The model receives these 18 ordered features:

| Sensor | Features |
|---|---|
| MAX30105 heart rate (7) | `hr_mean`, `hr_std`, `hr_min`, `hr_max`, `hr_range`, `hr_slope`, `hr_pnn_proxy` |
| GSR skin conductance (8) | `gsr_mean`, `gsr_std`, `gsr_min`, `gsr_max`, `gsr_range`, `gsr_slope`, `gsr_auc`, `gsr_peaks` |
| MLX90614 temperature (3) | `temp_mean`, `temp_std`, `temp_slope` |

`src/stress_detection/service/features/schema.py` is the canonical ordering. Training and live inference both call the same feature pipeline.

## Hardware wiring

| Component | ESP32 connection | Purpose |
|---|---|---|
| MAX30105 | I²C SDA GPIO 21, SCL GPIO 22, 3.3 V | Heart rate |
| MLX90614 | Same I²C bus, SDA GPIO 21, SCL GPIO 22, 3.3 V | Temperature |
| GSR sensor | Analog output to GPIO 34, module-appropriate supply | Skin conductance |

MAX30105 normally uses address `0x57`; MLX90614 normally uses `0x5A`, so they can share one I²C bus. Confirm module voltage and pull-ups before powering the device.

Detailed setup and packet rules are in [docs/hardware_setup.md](docs/hardware_setup.md) and [docs/hardware_serial_format.md](docs/hardware_serial_format.md).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/run_service.py
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The default input is the NodeMCU serial stream at `/dev/cu.usbserial-A5069RR4`. Close Arduino/PlatformIO serial monitors before starting the service because only one process can own the port. To run without hardware, set `input.source: synthetic` in `config/service.yaml`.

## Final trained model

The deployed v3 artifact contains two paths:

| Path | When used | Accuracy | Macro-F1 | Stress F1 | ROC-AUC |
|---|---|---:|---:|---:|---:|
| Personalized Extra Trees | Complete 120 s resting calibration | **95.65%** | **0.953** | **0.940** | **0.994** |
| Soft Voting fallback | No/incomplete calibration | 91.2% | 0.903 | 0.875 | 0.964 |

The personalized result is from nested leave-one-subject-out evaluation over
5,075 post-calibration WESAD windows from 15 subjects. In every outer fold,
Extra Trees parameters were selected using training subjects only. The held-out
person supplied only the same labelled two-minute resting baseline required by
the live application; those calibration windows were excluded from scoring.

These are held-out WESAD results, not clinical accuracy claims or a measured
95.65% result on the physical wearable. Complete the dashboard calibration
with a steady finger before starting a recording to enable the personalized
path. See [reports/personalized_model_report.md](reports/personalized_model_report.md).

## Rebuild data and models

The final artifacts use the 18-feature contract. Rebuild them in order:

```bash
.venv/bin/python scripts/build_interim.py
.venv/bin/python scripts/build_features.py
.venv/bin/python scripts/build_wesad_features.py
.venv/bin/python scripts/train_all_models.py --dataset wesad --version v2
.venv/bin/python scripts/train_personalized_model.py --version v3
```

The WESAD adapter uses only its wrist BVP, EDA, and temperature signals so public-data training matches the three-sensor hardware contract.

## Inputs and APIs

The service supports `synthetic`, `csv_replay`, `serial`, and newline-delimited JSON `tcp` sources. All normalize to:

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

See [docs/api.md](docs/api.md) for REST and WebSocket details.

## Verification

```bash
.venv/bin/pytest
cd frontend && npm test && npm run build
```

This is a research prototype, not a medical device. Its output is not a diagnosis.
# Hardware-only live monitor

To view your NodeMCU's live output separately from the main dashboard, first
close any other serial monitor (Arduino IDE / PlatformIO) that has the port
open, then run:

```bash
./scripts/run_hardware_monitor.sh
```

Open http://127.0.0.1:8765. The page reads
`/dev/cu.usbserial-A5069RR4` at 115200 baud, displays every raw serial line,
and updates cards for BPM, SpO2, object/ambient temperature, GSR, IR, and
finger detection.
