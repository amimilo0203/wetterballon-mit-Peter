"""
gdk101_radiation.py - FTLAB GDK101: gamma radiation sensor (I2C).

The GDK101 measures gamma and X-ray radiation with ten PIN photodiodes (it has
no Geiger tube). It measures on its own and reports a dose rate in microsievert
per hour (uSv/h) directly, so we only ask for the result.

Wiring:  +5V -> Pi 5 V pin, GND -> GND, SDA -> GPIO 2, SCL -> GPIO 3.
         The module needs 4.0 - 6.0 V on VCC, so 3.3 V is NOT enough. Its
         SDA/SCL lines run at 3.3 V, so they go straight to the Pi.
Address: 0x18 by default. Set with the A0/A1 pads (open = high), which are only
         read at power-on: 0x18 both short, 0x19 A0 open, 0x1A A1 open,
         0x1B both open.
Bus speed: the GDK101 is specified for 100 kHz, which is the Pi's default.
         Do not set i2c_arm_baudrate=400000 while it is on the bus.

Commands (FTLAB datasheet v1.5, "I2C INTERFACE"). Every command answers with
exactly 2 bytes:
  0xA0  reset               -> byte 0: 1 = ok, 0 = failed
  0xB0  status              -> byte 0: 0 = first ~10 s after power-on,
                                       1 = between 10 s and 10 min,
                                       2 = normal operation
                               byte 1: 1 = vibration detected, 0 = quiet
  0xB1  measuring time      -> byte 0 = minutes, byte 1 = seconds
  0xB2  dose rate, 10-minute average -> byte 0 = whole part, byte 1 = hundredths
  0xB3  dose rate, 1-minute average  -> byte 0 = whole part, byte 1 = hundredths
  0xB4  firmware version    -> byte 0 = major, byte 1 = minor
So 0x01 0x15 means 1 + 21/100 = 1.21 uSv/h. The two bytes are NOT a 16-bit
number, and there is no register map.

Two things matter for a balloon flight:
  * The sensor blanks its detection for about half a second whenever it feels a
    shock, and the payload swings the whole time. We therefore log the
    vibration flag in its own column so you can see which measurements to
    distrust. Mount the module on foam and leave the black sponge on its back.
  * The averages only update once per minute, and the values are small: at 12
    counts per minute and microsievert per hour, a normal background of
    0.1 uSv/h is barely one count per minute. Use the 10-minute average for
    anything you want to interpret, and treat the 1-minute average as noisy.

The old code in this repository read "register 0x00" and divided by 100. The
GDK101 has no such register; that value was meaningless.
"""

import time

import config
from sensors.base import Sensor


class GDK101Radiation(Sensor):
    NAME = "radiation"
    COLUMNS = ["radiation_10min_usvh", "radiation_1min_usvh",
               "radiation_uptime_min", "radiation_status", "radiation_vibration"]

    CMD_RESET = 0xA0
    CMD_STATUS = 0xB0
    CMD_MEASURING_TIME = 0xB1
    CMD_DOSE_10MIN = 0xB2
    CMD_DOSE_1MIN = 0xB3
    CMD_FIRMWARE = 0xB4

    # The sensor has its own small microcontroller that needs a moment to boot.
    STARTUP_TRIES = 12
    STARTUP_PAUSE_S = 1.0
    # Highest dose rate the sensor can report (datasheet: 0.01 - 200 uSv/h).
    MAX_DOSE_USVH = 200

    def __init__(self):
        from smbus2 import SMBus

        self.address = config.I2C_ADDR_GDK101
        self.bus = SMBus(config.I2C_BUS)

        # Ask for the firmware version until the sensor answers. Right after
        # power-on it needs about 10 seconds before it reacts at all, so we
        # keep trying instead of giving up on the first attempt.
        last_error = None
        for _ in range(self.STARTUP_TRIES):
            try:
                major, minor = self._query(self.CMD_FIRMWARE)
                self.firmware = f"{major}.{minor}"
                break
            except OSError as e:
                last_error = e
                time.sleep(self.STARTUP_PAUSE_S)
        else:
            raise IOError(f"no answer from the GDK101 at 0x{self.address:02X}: {last_error}")

        # DELIBERATELY NO RESET: a reset restarts the 10-minute averaging.
        # After a power cut the sensor has restarted on its own anyway.

    def read(self):
        status, vibration = self._query(self.CMD_STATUS)
        if status not in (0, 1, 2) or vibration not in (0, 1):
            raise ValueError(f"implausible status reply {status} {vibration}")

        minutes, seconds = self._query(self.CMD_MEASURING_TIME)
        return {
            "radiation_10min_usvh": self._dose(self.CMD_DOSE_10MIN),
            "radiation_1min_usvh": self._dose(self.CMD_DOSE_1MIN),
            "radiation_uptime_min": round(minutes + seconds / 60, 1),
            "radiation_status": status,        # 2 = warmed up, values trustworthy
            "radiation_vibration": vibration,  # 1 = shock, measurement interrupted
        }

    def _dose(self, command):
        """Reads one dose rate and converts [whole, hundredths] to a number."""
        whole, hundredths = self._query(command)
        if hundredths > 99 or whole > self.MAX_DOSE_USVH:
            raise ValueError(f"implausible dose reply {whole} {hundredths}")
        return round(whole + hundredths / 100, 2)

    def _query(self, command):
        """Sends a one-byte command and returns the two reply bytes."""
        data = self.bus.read_i2c_block_data(self.address, command, 2)
        time.sleep(0.01)  # the datasheet's example waits 10 ms between commands
        return data[0], data[1]

    def close(self):
        self.bus.close()
