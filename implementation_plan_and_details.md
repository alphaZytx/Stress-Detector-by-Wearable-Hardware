# Hardware-Aligned WESAD Retraining Plan

## First implementation status

The low-complexity first pass is implemented:

- the main service defaults to the live NodeMCU serial port;
- the labelled pipe-separated firmware output is parsed directly;
- the dashboard displays live BPM, live SpO2, object and ambient temperature, GSR, IR, and finger contact;
- `No finger` prevents a new stress prediction;
- WESAD retains its real wrist temperature and has fixed SpO2 plus neutral synthetic ambient-temperature compatibility columns;
- those two compatibility columns are not model inputs;
- only `svm_wesad_hardware_v1.joblib` was trained and configured for serving.

The trained SVM used 5,360 windows from 15 WESAD subjects. Leave-one-subject-out evaluation produced macro-F1 0.861 and stress recall 0.818. These are WESAD results, not proof of accuracy on the physical wearable.

## Goal

Train a new **binary stress / non-stress** model using only signals that are both:

1. available from the wearable, and
2. represented in the WESAD wrist dataset.

Example live message:

```text
BPM: 0 | SPO2: 0.0 | ObjTemp: 24.99 | AmbTemp: 27.12 | GSR: 100.76 | IR: 564 | No finger
```

## Recommended first model input

| Live field | Use in first WESAD model? | Why |
|---|---:|---|
| `BPM` | Yes | WESAD wrist BVP can be converted to BPM. |
| `GSR` | Yes | Corresponds to WESAD wrist EDA. |
| `ObjTemp` | Yes, after validation | Closest available match to WESAD wrist temperature if it measures skin-facing temperature. |
| `SPO2` | Display only | The dashboard shows the live sensor value. WESAD has no SpO2, so its compatibility column is fixed at 98 and excluded from training. |
| `AmbTemp` | Display only | WESAD does not provide ambient temperature. A neutral synthetic column may be retained for schema testing but is excluded from training. |
| `IR` | No, initially | WESAD does not provide the sensor's IR/raw optical level. Use it for signal quality. |
| `No finger` | No, but required as a gate | This is sensor status, not a physiological feature. Do not predict stress without finger contact. |

Do not add fields to the classifier just because the hardware exposes them. A model can only learn from a field when comparable labelled training data exists. Live SpO2 is displayed as reported by the hardware, while the fixed WESAD SpO2 and synthetic ambient-temperature columns are schema placeholders, not model inputs. SpO2, ambient temperature, and IR can become model features later only after collecting and labelling your own recordings.

## What already exists in this project

The current WESAD pipeline already maps:

- WESAD BVP -> derived `bpm`
- WESAD EDA -> `gsr`
- WESAD wrist temperature -> `temp_c`

It then creates 30-second rolling windows every 5 seconds and extracts heart-rate, GSR, and temperature summary features. The WESAD-only SVM training script evaluates by leaving entire subjects out, which is the correct evaluation direction.

The new work should produce a clearly versioned model, for example `svm_wesad_hardware_v2.joblib`, rather than overwrite the current model.

## Implementation steps

1. **Confirm the hardware schema and sampling rate.**
   Define one stable, machine-readable line format. The current project expects CSV:

   ```text
   timestamp,bpm,avg_bpm,gsr,temp_c
   ```

   Your shown `BPM: ... | ...` diagnostic format will not be parsed by the current serial reader. Either change firmware to emit the CSV contract, or extend the serial parser to explicitly parse this key/value format. Prefer CSV for reliability.

2. **Handle invalid finger readings before feature extraction.**
   When the device reports `No finger`, BPM is zero, or IR is below a calibrated contact threshold:

   - record the sample as invalid;
   - do not replace BPM with zero;
   - do not request a prediction for a window with insufficient valid BPM/contact samples;
   - display “Place finger correctly” instead of a stress result.

   Keep a contact-valid flag in the serial data even if it is not supplied to the classifier.

3. **Validate the temperature mapping.**
   WESAD temperature is a wrist/skin signal. Use `ObjTemp` only if the sensor is consistently aimed at skin and has believable skin-contact values. If it mostly measures room/background temperature, exclude temperature from both WESAD training and live inference. `AmbTemp` may be useful for later temperature compensation, but should not be used in the WESAD-only model.

4. **Build a hardware-compatible WESAD dataset.**
   Retain only the mapped one-second columns:

   ```text
   timestamp_ms, bpm, avg_bpm, gsr, temp_c, bpm_valid, label, subject_id
   ```

   Keep only WESAD `baseline` and `stress` labels. Drop transition, amusement, meditation, and unlabelled periods for this binary first version.

5. **Use the same live and training feature code.**
   Build the exact same 30-second features from WESAD and incoming serial samples. The classifier should receive the same ordered feature list at training and runtime. Recommended first feature groups:

   - BPM: mean, standard deviation, min/max, range, trend, beat-change proxy
   - GSR: mean, variation, range, trend, area, response peaks
   - Object/skin temperature: mean, variation, trend (only if Step 3 passes)

6. **Train one model first.**
   Start with only the existing SVM pipeline. Use subject-held-out macro-F1, stress recall, and false-positive rate; do not judge it by training accuracy. Train a second model only after the full physical-device path works reliably, and leave the remaining models/ensembles for a later comparison.

7. **Evaluate honestly.**
   Use leave-one-subject-out evaluation on WESAD. All windows from one person must remain together in the test fold. Report the number of subjects, windows, selected fields, feature names, confusion matrix, macro-F1, stress recall, and calibration/threshold used.

8. **Test the full live path.**
   Feed recorded serial lines through the actual parser, feature streamer, and saved model. Test: normal contact, no finger, BPM zero, malformed line, missing samples, and a 30-second valid recording. Confirm the deployed app loads the new model version and does not silently use an old ensemble.

9. **Collect a small local labelled calibration dataset.**
   WESAD is a useful starting point, but it is not the same device, placement, sensor scale, or users. Record repeated baseline and controlled stress/task sessions from your own hardware. Use this first for distribution checks and personal calibration; later use subject-separated local data to fine-tune or replace the WESAD-only model.

## Important complications

- **Domain mismatch:** WESAD uses a research wrist device; your BPM comes from a MAX3010x-type optical sensor, GSR may be ADC counts rather than microSiemens, and the temperature sensor/device placement differs. Scaling makes numeric ranges comparable but cannot fully make the physiology or noise identical.
- **BPM is missing frequently in WESAD and live data:** WESAD BPM is derived from BVP, while your sensor produces a device estimate. Both need quality checks. A single zero BPM must never look like an unusually low heart rate.
- **One reading is not enough:** Stress inference needs a time window. At the current project settings, wait for about 30 seconds of valid data before the first prediction, then refresh every 5 seconds.
- **GSR depends on contact and environment:** Loose electrodes, dry skin, movement, and sensor warm-up can dominate GSR. Add a settling/contact check and consider a per-person baseline calibration.
- **Temperature can be misleading:** Object temperature can measure the sensor, clothing, or background instead of skin. Ambient temperature changes can affect it; do not call it skin temperature unless verified.
- **SpO2 is not a free extra feature:** It should not be passed to a WESAD-trained model. Its common zero/no-finger behaviour can create misleading shortcuts if included without matching labelled data.
- **Dataset labels are protocol labels:** WESAD “stress” represents a controlled laboratory stress condition, not a universal clinical diagnosis. The UI and report should say “estimated stress state” and not make medical claims.
- **Leakage risk:** Randomly splitting overlapping 30-second windows will inflate performance. Split by participant before window-level evaluation.
- **Serial incompatibility:** The existing application currently expects CSV, not the pipe-separated labelled status line shown above. This must be addressed before live inference.

## Suggested delivery order

1. Stabilise firmware output and validate contact/BPM/GSR/temperature readings.
2. Add contact/quality gating and the parser update.
3. Create the reduced hardware-compatible WESAD feature dataset.
4. Train `v2`, evaluate with leave-one-subject-out, and save metrics plus feature contract.
5. Wire `v2` into the live service and perform replay plus physical-device tests.
6. Gather local labelled recordings and reassess model transfer before claiming real-world accuracy.

## Definition of done

The implementation is ready for use when a connected device can provide at least 30 seconds of valid finger-contact samples, the service extracts exactly the same feature schema used during training, the new versioned model returns a probability/prediction, invalid contact returns a clear no-prediction status, and the model's held-out WESAD results and hardware limitations are documented.
