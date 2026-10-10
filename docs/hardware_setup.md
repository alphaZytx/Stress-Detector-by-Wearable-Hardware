# Three-Sensor Hardware Setup

## Bill of materials

| Component | Role |
|---|---|
| ESP32 DevKit | Sampling and USB serial transport |
| MAX30105 | Optical heart-rate sensing |
| GSR sensor | Skin-conductance sensing |
| MLX90614 | Temperature sensing |

## Suggested ESP32 wiring

| Module pin | ESP32 pin |
|---|---|
| MAX30105 SDA | GPIO 21 |
| MAX30105 SCL | GPIO 22 |
| MLX90614 SDA | GPIO 21 |
| MLX90614 SCL | GPIO 22 |
| GSR analog output | GPIO 34 (ADC input) |
| All grounds | Common GND |

MAX30105 (`0x57`) and MLX90614 (`0x5A`) normally have different addresses and can share the I²C bus. Use 3.3 V-compatible breakout boards and verify the GSR module's supply/output range before connecting it to the ESP32 ADC.

## Firmware output

Initialize both I²C sensors, sample the GSR ADC, and emit one line per second:

```text
timestamp,bpm,avg_bpm,gsr,temp_c
```

Configure the application in `config/service.yaml`:

```yaml
input:
  source: serial
  serial:
    port: /dev/tty.usbserial-0001
    baudrate: 115200
```

Confirm the exact device port, start the service, and use the dashboard raw-sensor monitor to verify all three readings. See `hardware_first_run.md` for the checklist.
