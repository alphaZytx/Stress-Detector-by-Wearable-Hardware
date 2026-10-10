# System Explanation — Three-Sensor Revision

The wearable now uses only MAX30105 heart rate, GSR skin conductance, and MLX90614 temperature. A normalized sample contains `timestamp_ms`, `bpm`, `avg_bpm`, `gsr`, `temp_c`, and optional `source_label`.

Samples arrive at 1 Hz. The pipeline keeps 30 samples, advances by 5 samples, validates heart rate, and calculates an ordered 18-feature vector: 7 heart-rate features, 8 GSR features, and 3 temperature features. That same extractor is used offline and live.

The configured base model or ensemble returns baseline/stress probabilities. The service smooths results, broadcasts them over WebSocket, and can persist the three raw sensor values with session predictions. The dashboard shows only heart rate, GSR, and temperature gauges, and its raw monitor mirrors the five-field serial protocol.

For the detailed contracts, see `README.md`, `docs/api.md`, `docs/hardware_setup.md`, and `docs/hardware_serial_format.md`.
