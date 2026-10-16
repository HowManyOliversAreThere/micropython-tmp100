"""
MicroPython driver for the Texas Instruments TMP100 and TMP101 digital
temperature sensors (I2C, 9- to 12-bit resolution).

I2C address (7-bit): 0x48 to 0x4F, set by the ADD0/ADD1 pins (TMP100)
or ADD0 (TMP101). Both TMP100 address pins tied to GND gives 0x48.

Quick start
-----------
    from machine import I2C, Pin
    import tmp100

    i2c = I2C(0, sda=Pin(19), scl=Pin(20), freq=400_000)
    sensor = tmp100.TMP100(i2c)          # 0x48, 12-bit
    print(sensor.temperature())          # degrees C

    sensor.shutdown()                    # < 1 uA between readings
    print(sensor.one_shot())             # wake, convert once, sleep again
"""

import time
from micropython import const

ADDR_DEFAULT = 0x48

# Resolution in bits -> R1:R0 bits and the worst-case conversion time (ms).
_RESOLUTIONS = {9: (0, 75), 10: (1, 150), 11: (2, 300), 12: (3, 600)}

_REG_TEMP = const(0x00)
_REG_CONFIG = const(0x01)
_REG_TLOW = const(0x02)
_REG_THIGH = const(0x03)

_CFG_SD = const(0x01)  # shutdown
_CFG_TM = const(0x02)  # thermostat mode (TMP101 ALERT pin): 1 = interrupt
_CFG_POL = const(0x04)  # ALERT polarity (TMP101): 1 = active high
_CFG_OS = const(0x80)  # one-shot (write) / ALERT state (read)


class TMP100:
    def __init__(self, i2c, address=ADDR_DEFAULT, resolution=12):
        """
        i2c        : machine.I2C (or SoftI2C) instance
        address    : 0x48..0x4F
        resolution : 9, 10, 11 or 12 bits. Higher is slower: 12 bits
                     takes up to 600 ms per conversion.
        Raises OSError if nothing answers at the address.
        """
        self._i2c = i2c
        self._addr = address
        self._buf2 = bytearray(2)
        self._buf1 = bytearray(1)
        self._config = 0
        self.resolution(resolution)

    # ---- Low-level I2C ----------------------------------------------------
    def _read_config(self):
        self._i2c.readfrom_mem_into(self._addr, _REG_CONFIG, self._buf1)
        return self._buf1[0]

    def _write_config(self, value):
        self._config = value & 0xFF
        self._i2c.writeto_mem(self._addr, _REG_CONFIG, bytes((self._config & ~_CFG_OS,)))

    @staticmethod
    def _to_celsius(msb, lsb):
        raw = (msb << 4) | (lsb >> 4)
        if raw & 0x800:
            raw -= 0x1000
        return raw / 16

    @staticmethod
    def _from_celsius(celsius):
        raw = int(round(celsius * 16)) & 0xFFF
        return bytes(((raw >> 4) & 0xFF, (raw << 4) & 0xF0))

    # ---- Configuration ----------------------------------------------------
    def resolution(self, bits=None):
        """Get or set the conversion resolution (9-12 bits)."""
        if bits is None:
            return 9 + ((self._read_config() >> 5) & 0x03)
        if bits not in _RESOLUTIONS:
            raise ValueError("resolution must be 9..12 bits")
        cfg = (self._read_config() & ~0x60 & ~_CFG_OS) | (_RESOLUTIONS[bits][0] << 5)
        self._write_config(cfg)
        self._bits = bits
        return bits

    @property
    def conversion_ms(self):
        """Worst-case time for one conversion at the current resolution."""
        return _RESOLUTIONS[self._bits][1]

    def check(self):
        """True if the device answers and its configuration register
        reads back what was last written to it. The TMP100 has no ID
        register, so this is the closest thing to an identity check."""
        try:
            return (self._read_config() & 0x7F) == (self._config & 0x7F)
        except OSError:
            return False

    # ---- Readings ---------------------------------------------------------
    def temperature(self):
        """Most recent conversion, in degrees C. Reads 0.0 until the
        first conversion after power-up has finished."""
        self._i2c.readfrom_mem_into(self._addr, _REG_TEMP, self._buf2)
        return self._to_celsius(self._buf2[0], self._buf2[1])

    # ---- Power ------------------------------------------------------------
    def shutdown(self):
        """Stop converting (< 1 uA). The last reading stays readable."""
        self._write_config(self._config | _CFG_SD)

    def wake(self):
        """Go back to continuous conversion."""
        self._write_config(self._config & ~_CFG_SD)

    @property
    def is_shutdown(self):
        return bool(self._config & _CFG_SD)

    def one_shot(self, wait=True):
        """From shutdown, run a single conversion and go back to sleep.
        With wait=True, blocks until it's done and returns the reading.
        Raises ValueError if not shut down."""
        if not self._config & _CFG_SD:
            raise ValueError("one_shot() needs shutdown() first")
        self._i2c.writeto_mem(self._addr, _REG_CONFIG, bytes((self._config | _CFG_OS,)))
        if not wait:
            return None
        # The datasheet doesn't promise OS/ALERT reads back as a "done"
        # flag on both parts, so wait out the worst-case conversion time.
        time.sleep_ms(self.conversion_ms)
        return self.temperature()

    # ---- Thermostat limits (drive the TMP101's ALERT pin) -----------------
    def limits(self, low=None, high=None):
        """Get or set the T(LOW)/T(HIGH) thermostat limits in degrees C.
        Returns (low, high)."""
        if low is not None:
            self._i2c.writeto_mem(self._addr, _REG_TLOW, self._from_celsius(low))
        if high is not None:
            self._i2c.writeto_mem(self._addr, _REG_THIGH, self._from_celsius(high))
        self._i2c.readfrom_mem_into(self._addr, _REG_TLOW, self._buf2)
        lo = self._to_celsius(self._buf2[0], self._buf2[1])
        self._i2c.readfrom_mem_into(self._addr, _REG_THIGH, self._buf2)
        return lo, self._to_celsius(self._buf2[0], self._buf2[1])

    def alert(self):
        """State of the thermostat comparator (the TMP101's ALERT output,
        before polarity)."""
        return bool(self._read_config() & _CFG_OS)
