# Report Narrative — Three-Sensor Design

The revised wearable uses MAX30105 heart rate, GSR skin conductance, and MLX90614 temperature. The ESP32 streams a five-field summary at 1 Hz to a FastAPI service. The service forms 30-second windows every 5 seconds and extracts 18 features: seven heart-rate statistics, eight GSR statistics, and three temperature statistics.

Offline training and live inference share the same extractor and canonical feature order. Public WESAD training data is restricted to wrist BVP, EDA, and temperature so its input channels align with the deployed hardware. The project recordings and WESAD still differ in GSR units, so cross-device transfer remains a limitation.

The React dashboard exposes the three sensor gauges, heart-rate trend and variability proxy, model input vector, raw packet stream, stress probability, session history, calibration, and breathing guidance. Calibration stores resting means for the same three signals.

The v4 base-model and ensemble artifacts were rebuilt against the 18-feature contract. Older artifacts are intentionally incompatible and rejected by schema guards.
