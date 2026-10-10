# First Hardware Run

1. Check that MAX30105 and MLX90614 are detected on the shared I²C bus, normally at `0x57` and `0x5A`.
2. Confirm the GSR output never exceeds the ESP32 ADC input range.
3. Open a serial monitor at 115200 baud and verify one packet per second in this exact order:

   ```text
   timestamp,bpm,avg_bpm,gsr,temp_c
   ```

4. Place a finger steadily over MAX30105 and wait for valid 40–200 BPM readings.
5. Attach the GSR electrodes and confirm the value responds gradually rather than sticking at an ADC rail.
6. Aim/place MLX90614 consistently and verify plausible temperature readings.
7. Set `input.source: serial` and the correct port in `config/service.yaml`.
8. Start the backend and frontend. The raw monitor and three gauge cards should update once per second; the first prediction should appear after the 30-second buffer fills.

Malformed or incomplete packets are skipped. If predictions never start, check that at least 70% of BPM readings in each window are valid.
