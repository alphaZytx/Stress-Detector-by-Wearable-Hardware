# Presentation Brief — Three-Sensor Wearable

Present the system as a research prototype built around exactly three sensors:

- MAX30105 heart rate
- GSR skin conductance
- MLX90614 temperature

Show the pipeline as: three sensors → ESP32 at 1 Hz → quality checks → 30-second window with 5-second stride → 18 features → classifier/ensemble → smoothing → dashboard and breathing guidance.

Use proof points that match the v4 artifacts: 18 features, 16 training subjects, and train/serve feature parity. Do not show retired hardware or stale metrics from earlier feature schemas.
