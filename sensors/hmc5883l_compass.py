"""
hmc5883l_compass.py - HMC5883L: magnetometer / compass (I2C, address 0x1E).

Measures the magnetic field in three directions (X, Y, Z). From that we
compute the compass heading. Caution: the heading is only correct when the
sensor is level. For a balloon that spins and swings, the interesting part
is HOW it rotates, not the exact value.

Wiring: SDA -> GPIO 2, SCL -> GPIO 3, VCC -> 3.3 V, GND -> GND.

Common pitfall: many modules labelled "HMC5883L" (e.g. GY-271) actually
contain a QMC5883L. That chip answers at address 0x0D and has different
registers. If i2cdetect shows 0x0D instead of 0x1E, you need another driver.
"""

import math

import config
from sensors.base import Sensor


class HMC5883LCompass(Sensor):
    NAME = "hmc5883l"
    COLUMNS = ["mag_x_ut", "mag_y_ut", "mag_z_ut", "heading_deg"]

    # Registers (datasheet)
    REG_CONFIG_A = 0x00
    REG_CONFIG_B = 0x01
    REG_MODE = 0x02
    REG_DATA = 0x03      # 6 bytes from here: X high, X low, Z high, Z low, Y high, Y low

    # Settings
    CONFIG_A_VALUE = 0x70  # average 8 samples, 15 Hz data rate, normal measurement
    CONFIG_B_VALUE = 0x20  # gain: 1090 LSB per gauss (default, +/- 1.3 gauss range)
    MODE_CONTINUOUS = 0x00

    LSB_PER_GAUSS = 1090
    MICROTESLA_PER_GAUSS = 100
    OVERFLOW = -4096       # the sensor returns -4096 when a value was out of range

    def __init__(self):
        from smbus2 import SMBus

        self.address = config.I2C_ADDR_HMC5883L
        self.bus = SMBus(config.I2C_BUS)
        self.bus.write_byte_data(self.address, self.REG_CONFIG_A, self.CONFIG_A_VALUE)
        self.bus.write_byte_data(self.address, self.REG_CONFIG_B, self.CONFIG_B_VALUE)
        self.bus.write_byte_data(self.address, self.REG_MODE, self.MODE_CONTINUOUS)

    def read(self):
        # Read all 6 data bytes in one go (order is X, Z, Y - not X, Y, Z!)
        data = self.bus.read_i2c_block_data(self.address, self.REG_DATA, 6)
        x = self._to_signed(data[0], data[1])
        z = self._to_signed(data[2], data[3])
        y = self._to_signed(data[4], data[5])

        if self.OVERFLOW in (x, y, z):
            raise ValueError("magnetic field too strong, sensor saturated (magnet nearby?)")

        return {
            "mag_x_ut": round(self._to_microtesla(x), 2),
            "mag_y_ut": round(self._to_microtesla(y), 2),
            "mag_z_ut": round(self._to_microtesla(z), 2),
            "heading_deg": round(self._heading(x, y), 1),
        }

    @staticmethod
    def _to_signed(high, low):
        """Combines two bytes into a number from -32768 to 32767."""
        value = (high << 8) | low
        if value >= 32768:
            value -= 65536
        return value

    def _to_microtesla(self, raw):
        return raw / self.LSB_PER_GAUSS * self.MICROTESLA_PER_GAUSS

    @staticmethod
    def _heading(x, y):
        """Heading in degrees (0 = north, 90 = east), including the declination from config."""
        degrees = math.degrees(math.atan2(y, x)) + config.MAGNETIC_DECLINATION_DEG
        return degrees % 360

    def close(self):
        self.bus.close()
