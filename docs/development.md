# Developer Guide

How to extend and maintain the project. Conventions (from `CLAUDE.md`): Python
3.11+, type hints on public functions, `logging` (no `print` in library code),
all paths via `config.paths.*`, scikit-learn only (no torch/tf), tests run from
the repo root with pytest.

## Add a new sensor to the pipeline

The sample schema and the feature set are the two contracts to update together.

## Run without hardware

`config/service.yaml` defaults to `input.source: synthetic`. The source emits a
seeded, randomised baseline → stress → recovery cycle using the same sample
schema as the ESP32. Start the backend and frontend normally; predictions are
made by the deployed SVM, not by the generator:

```bash
python3 scripts/run_service.py
cd frontend && pnpm dev
```

Tune `input.synthetic.speed` to change wall-clock speed, phase durations with
`baseline_s`, `stress_s`, and `recovery_s`, or `seed` to produce another
reproducible stream. Set `input.source: csv_replay` to use recorded data instead.

1. **Sample schema.** Add the field to `SensorSample`
   (`src/stress_detection/service/sources/base.py`) and populate it in each source
   that can emit it (`csv_replay.py`, `serial_source.py`, `tcp_source.py`).
2. **Buffer columns.** If a feature needs the new field, add it to
   `_BUFFER_COLUMNS` in `service/features/streamer.py` so it reaches
   `build_feature_table()`.
3. **Feature extraction.** Add the extractor in
   `src/stress_detection/features/extractors.py` and wire it into
   `features/pipeline.py:build_feature_table()`.
4. **Canonical order.** Append the new feature name to `FEATURE_COLUMNS`
   (`service/features/schema.py`). **This order is the model's input contract** -
   the `InferenceEngine` validates `n_features_in_` against it.
5. **Retrain** (the model's `n_features_in_` changes), then update any tests that
   assert the feature count (currently 22).

## Retrain the models with new data

1. Rebuild features: `python3 scripts/build_features.py` (project) and
   `python3 scripts/build_wesad_features.py` (WESAD) → parquets in `data/features/`.
2. Train (versioned, non-destructive - `--version` defaults to `v1`):
   ```bash
   python3 scripts/train_wesad_only.py --version v3
   python3 scripts/train_combined.py   --version v3
   ```
   Each writes `data/models/svm_<name>_v3.joblib`, `reports/metrics_<name>_v3.json`,
   `reports/confusion_<name>_v3.png`, and records the fitted SVC hyperparameters.
3. Regenerate report artifacts (figures + `SUMMARY.md` + `headline_metrics.csv`):
   ```bash
   python3 scripts/build_report_artifacts.py --version v3
   ```
4. Point the service at the new model: `inference.model_path` in
   `config/service.yaml`.
5. Sanity-check transfer to the project hardware:
   `python3 scripts/check_model_transfer.py --version v3`.
6. If the demo asset's behaviour matters, regenerate it
   (`python3 scripts/build_demo_session.py`) and confirm
   `tests/test_service/test_demo.py` still passes.

## Add a new React route

1. Create the page under `frontend/src/routes/`.
2. Register it in the router (look for the protected-route block alongside `/live`,
   `/history`, etc.) behind `ProtectedRoute` + `AppShell`.
3. Server state via TanStack Query hooks (`src/hooks/useSessions.ts` pattern); REST
   calls via `src/api/*` (typed against `src/api/types.ts`); WS/live state via the
   Zustand `liveStore`.
4. Add a Vitest component test in `frontend/tests/` and, if it's a user flow, an
   e2e `.mjs` script.

## Test taxonomy

| Where | Kind | Run | Covers |
|-------|------|-----|--------|
| `tests/test_*.py` | pytest (unit) | `python3 -m pytest` | Phase 1 ML: loader, cleaner, windowing, extractors, pipeline, WESAD, SVM, reports |
| `tests/test_service/` | pytest (unit/integration) | `python3 -m pytest` | service: sources, streamer, inference, sessions, auth, ws routes, demo asset guard |
| `frontend/tests/*.test.tsx`, `*.test.ts` | Vitest (component/unit) | `cd frontend && pnpm test` | components (Live, ConnectionPill, StressAlert) + lib (calibration, breathing, liveStore) |
| `frontend/tests/e2e_*.mjs` | Playwright (e2e) | `node tests/e2e_<x>.mjs` (needs backend + vite up) | full flows: fullstack, history, calibration, breathing, settings, reconnect, demo, failure-modes |

Current counts: **backend 160** pytest, **frontend 20** Vitest. The e2e `.mjs`
scripts are run manually against a live stack (raise `csv_replay.speed` to 10 for
speed); `e2e_demo_alert.mjs` is **headed-only** (headless throttles the 1 Hz replay).

## AI-assisted development workflow (CLAUDE.md / HANDOFF.md)

This project was built with Claude Code across phases. Two files anchor that:

- **`CLAUDE.md`** - durable project context (what it is, hardware facts, data facts,
  conventions, don'ts). Read at the start of every session; rarely changes.
- **`HANDOFF.md`** - session-to-session continuity log: current phase, what was just
  completed, key findings (e.g. the model-transfer "critical finding"), deferred
  TODOs, and exact next steps. Updated **between** subphases so any session can
  resume cleanly.

When extending the project with an AI agent: have it read both first, work in small
verified steps (each phase has an exit gate that must pass before moving on), and
update `HANDOFF.md` before ending. Don't re-derive model numbers from memory - read
`reports/SUMMARY.md` / `reports/headline_metrics.csv`.
