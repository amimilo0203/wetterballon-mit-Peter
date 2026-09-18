"""
as7265x_spectral.py - AS7265x (SparkFun Triad): 18-channel spectral sensor (I2C).

The board contains three chips (AS72651, AS72652, AS72653) that together
measure the light intensity at 18 wavelengths from 410 nm (violet) to 940 nm
(near infrared). We read the *calibrated* values, which the sensor firmware
reports in microwatts per square centimetre (uW/cm2).

Wiring: SDA -> GPIO 2, SCL -> GPIO 3, 3V3 -> 3.3 V, GND -> GND. Address 0x49.

How talking to this sensor works (this is the tricky part)
----------------------------------------------------------
The sensor has only three "real" I2C registers: STATUS, WRITE and READ.
All interesting registers (called "virtual registers") are reached through
them with a small handshake:
  * to write:  wait until TX_VALID is clear, write (address | 0x80) into WRITE,
               wait again, write the value into WRITE
  * to read:   wait until TX_VALID is clear, write the address into WRITE,
               wait until RX_VALID is set, read the value from READ
The three chips share these registers. Which chip you are talking to is
chosen with the virtual register DEV_SELECT (0x4F).

Measuring works like this: set the measurement mode to "one-shot, all
channels" (this starts a measurement), wait until the DATA_READY bit is set,
then read 6 floats (4 bytes each, big-endian) from every chip.

Every waiting loop has a timeout. The original code had "while True" loops
that would freeze the whole program forever if the sensor stopped answering.
"""

import struct
import time

import config
from sensors.base import Sensor, wait_until


class AS7265xSpectral(Sensor):
    NAME = "as7265x"

    # The three chips on the board and the wavelengths (nm) of the 6 values
    # each one delivers, in the order the values are stored in its registers.
    DEVICE_NIR = 0x00       # AS72651 (master), channels R S T U V W
    DEVICE_VISIBLE = 0x01   # AS72652,          channels G H I J K L
    DEVICE_UV = 0x02        # AS72653,          channels A B C D E F
    WAVELENGTHS_NM = {
        DEVICE_NIR: [610, 680, 730, 760, 810, 860],
        DEVICE_VISIBLE: [560, 585, 645, 705, 900, 940],
        DEVICE_UV: [410, 435, 460, 485, 510, 535],
    }
    ALL_WAVELENGTHS_NM = sorted(nm for group in WAVELENGTHS_NM.values() for nm in group)
    COLUMNS = [f"spectrum_{nm}nm" for nm in ALL_WAVELENGTHS_NM]

    # Real I2C registers
    REG_STATUS = 0x00
    REG_WRITE = 0x01
    REG_READ = 0x02
    TX_VALID = 0x02   # bit in STATUS: sensor is still busy with the last write
    RX_VALID = 0x01   # bit in STATUS: a reply byte is ready in READ

    # Virtual registers
    VREG_DEVICE_TYPE = 0x00     # must read 0x40 for an AS7265x
    VREG_CONTROL_SETUP = 0x04   # bit 7 reset, bits 5:4 gain, bits 3:2 mode, bit 1 data ready
    VREG_INTEGRATION_TIME = 0x05
    VREG_LED_CONFIG = 0x07      # bit 3 LED on/off, bits 5:4 LED current, bit 0 indicator LED
    VREG_CALIBRATED_DATA = 0x14 # 6 floats = 24 bytes from here
    VREG_DEVICE_SELECT = 0x4F

    DEVICE_TYPE_AS7265X = 0x40
    RESET_BIT = 0x80
    DATA_READY_BIT = 0x02
    MODE_ONE_SHOT_ALL_CHANNELS = 3   # (mode 2 would be continuous)
    GAIN_1X = 0                      # 0 = 1x, 1 = 3.7x, 2 = 16x, 3 = 64x
    INTEGRATION_CYCLES = 49          # 49 * 2.8 ms = 137 ms per bank; one-shot needs 2 banks
    LED_CONFIG_ALL_OFF = 0x00
    LED_CONFIG_ON_12MA = 0x08        # LED on, lowest current (12.5 mA), indicator LED off

    HANDSHAKE_TIMEOUT_S = 1.0
    MEASUREMENT_TIMEOUT_S = 5.0

    def __init__(self):
        from smbus2 import SMBus

        self.address = config.I2C_ADDR_AS7265X
        self.bus = SMBus(config.I2C_BUS)

        device_type = self._read_virtual(self.VREG_DEVICE_TYPE)
        if device_type != self.DEVICE_TYPE_AS7265X:
            raise IOError(f"unexpected device type 0x{device_type:02X} (expected 0x40)")

        self._write_virtual(self.VREG_CONTROL_SETUP, self.RESET_BIT)
        time.sleep(1.0)  # the sensor needs a moment after the reset

        led_config = self.LED_CONFIG_ON_12MA if config.AS7265X_LEDS_ON else self.LED_CONFIG_ALL_OFF
        for device in (self.DEVICE_NIR, self.DEVICE_VISIBLE, self.DEVICE_UV):
            self._select_device(device)
            self._write_virtual(self.VREG_LED_CONFIG, led_config)
            self._write_virtual(self.VREG_INTEGRATION_TIME, self.INTEGRATION_CYCLES)
            self._set_gain(self.GAIN_1X)
        self._select_device(self.DEVICE_NIR)

    def read(self):
        self._start_measurement()
        wait_until(self._data_ready, self.MEASUREMENT_TIMEOUT_S,
                   poll_interval_s=0.01, description="AS7265x data ready")

        values = {}
        for device, wavelengths in self.WAVELENGTHS_NM.items():
            self._select_device(device)
            for nm, value in zip(wavelengths, self._read_calibrated_floats()):
                values[f"spectrum_{nm}nm"] = round(value, 3)
        return values

    def close(self):
        try:
            for device in (self.DEVICE_NIR, self.DEVICE_VISIBLE, self.DEVICE_UV):
                self._select_device(device)
                self._write_virtual(self.VREG_LED_CONFIG, self.LED_CONFIG_ALL_OFF)
        except Exception:
            pass
        self.bus.close()

    # ------------------------------------------------------------- measuring

    def _start_measurement(self):
        """Writing the one-shot mode into CONTROL_SETUP starts a new measurement."""
        self._select_device(self.DEVICE_NIR)
        value = self._read_virtual(self.VREG_CONTROL_SETUP)
        value = (value & 0b11110011) | (self.MODE_ONE_SHOT_ALL_CHANNELS << 2)
        self._write_virtual(self.VREG_CONTROL_SETUP, value)

    def _data_ready(self):
        return bool(self._read_virtual(self.VREG_CONTROL_SETUP) & self.DATA_READY_BIT)

    def _set_gain(self, gain):
        value = self._read_virtual(self.VREG_CONTROL_SETUP)
        value = (value & 0b11001111) | (gain << 4)
        self._write_virtual(self.VREG_CONTROL_SETUP, value)

    def _select_device(self, device):
        self._write_virtual(self.VREG_DEVICE_SELECT, device)

    def _read_calibrated_floats(self):
        """Reads the 6 calibrated values (24 bytes) of the currently selected chip."""
        raw = bytes(self._read_virtual(self.VREG_CALIBRATED_DATA + i) for i in range(24))
        return struct.unpack(">6f", raw)   # ">" = big-endian, "6f" = six floats

    # ------------------------------------------------------------- handshake

    def _status(self):
        return self.bus.read_byte_data(self.address, self.REG_STATUS)

    def _wait_tx_free(self):
        wait_until(lambda: not (self._status() & self.TX_VALID),
                   self.HANDSHAKE_TIMEOUT_S, description="AS7265x ready for write")

    def _wait_rx_ready(self):
        wait_until(lambda: self._status() & self.RX_VALID,
                   self.HANDSHAKE_TIMEOUT_S, description="AS7265x reply")

    def _read_virtual(self, virtual_register):
        # If a stale reply is still waiting, read it away first.
        if self._status() & self.RX_VALID:
            self.bus.read_byte_data(self.address, self.REG_READ)
        self._wait_tx_free()
        self.bus.write_byte_data(self.address, self.REG_WRITE, virtual_register)
        self._wait_rx_ready()
        return self.bus.read_byte_data(self.address, self.REG_READ)

    def _write_virtual(self, virtual_register, value):
        self._wait_tx_free()
        self.bus.write_byte_data(self.address, self.REG_WRITE, virtual_register | 0x80)
        self._wait_tx_free()
        self.bus.write_byte_data(self.address, self.REG_WRITE, value)
