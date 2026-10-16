# TMP100 / TMP101 temperature sensor

A MicroPython driver for the Texas Instruments **TMP100** and **TMP101**
I2C digital temperature sensors: 9- to 12-bit readings (down to
0.0625 °C), shutdown and one-shot modes, and the thermostat limits that
drive the TMP101's ALERT pin.

Copy `tmp100.py` onto your board, or install it with `mip`:

```python
import mip
mip.install("github:HowManyOliversAreThere/micropython-tmp100")
```

## Usage

```python
from machine import I2C, Pin
import tmp100

i2c = I2C(0, sda=Pin(19), scl=Pin(20), freq=400_000)
sensor = tmp100.TMP100(i2c, address=0x48, resolution=12)
print(sensor.temperature())     # °C

# Low power: sleep between readings.
sensor.shutdown()
print(sensor.one_shot())        # converts once, waits, returns °C
```

## Notes

- The address is 0x48 to 0x4F, depending on the ADD0/ADD1 pins (TMP100)
  or ADD0 (TMP101). Check your datasheet's table, since ADD pins can also
  be left floating for some addresses.
- 12-bit conversions take up to 600 ms, and the first reading after
  power-up is 0.0 °C until a conversion finishes.
- The part has no ID register. `check()` confirms the device still
  answers and holds the configuration it was given.

## License

MIT - see [LICENSE](LICENSE).
