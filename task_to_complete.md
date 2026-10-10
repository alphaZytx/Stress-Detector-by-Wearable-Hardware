# Current Project Contract

The hardware and software target exactly three sensors: MAX30105 heart rate, GSR skin conductance, and MLX90614 temperature.

Required invariants:

- five-field serial packets: `timestamp,bpm,avg_bpm,gsr,temp_c`
- normalized samples containing only the three sensor channels plus timestamp/source metadata
- 30-second windows, 5-second stride, 1 Hz input
- 18 ordered model features (7 HR, 8 GSR, 3 temperature)
- Python, TypeScript, persistence, demo, docs, tests, and model artifacts kept in sync

The v4 model artifacts implement this contract.
