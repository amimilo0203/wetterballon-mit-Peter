"""
bme280_environment.py - BME280: temperature, humidity and air pressure (I2C).

Wiring:  SDA -> GPIO 2, SCL -> GPIO 3, VCC -> 3.3 V, GND -> GND.
Address: usually 0x76, some modules 0x77 (see config.I2C_ADDR_BME280).

We use the ready-made library from Pimoroni ("pimoroni-bme280"), which does
the complicated conversion of the raw values for us.

Limits of this sensor (important for a balloon flight!):
  * pressure range 300 - 1100 hPa  -> above roughly 9 km the value stops
    making sense (300 hPa is reached at about 9 km altitude)
  * temperature range -40 - +85 C  -> the stratosphere can be colder
"""

import time

import config
from sensors.base import Sensor


class BME280Environment(Sensor):
    NAME = "bme280"
    COLUMNS = ["temperature_c", "humidity_pct", "pressure_hpa"]

    def __init__(self):
        # Imports inside __init__ so that the simulation mode works on a PC
        # where these Raspberry Pi libraries are not installed.
        from smbus2 import SMBus
        from bme280 import BME280

        self.bus = SMBus(config.I2C_BUS)
        self.sensor = BME280(i2c_dev=self.bus, i2c_addr=config.I2C_ADDR_BME280)

        # The first reading after power-on is often garbage with this sensor,
        # so read once, wait briefly and throw the values away.
        self.sensor.get_temperature()
        time.sleep(0.1)

    def read(self):
        return {
            "temperature_c": round(self.sensor.get_temperature(), 2),
            "humidity_pct": round(self.sensor.get_humidity(), 2),
            "pressure_hpa": round(self.sensor.get_pressure(), 2),
        }

    def close(self):
        self.bus.close()
