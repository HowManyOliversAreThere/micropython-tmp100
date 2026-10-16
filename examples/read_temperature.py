"""Print the temperature once a second, sleeping the sensor in between."""

import time
from machine import I2C, Pin

import tmp100

i2c = I2C(0, sda=Pin(19), scl=Pin(20), freq=400_000)
sensor = tmp100.TMP100(i2c)
sensor.shutdown()

while True:
    print("{:.2f} °C".format(sensor.one_shot()))
    time.sleep(1)
