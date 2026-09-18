"""
mhz19_co2.py - MH-Z19 (B/C): CO2 sensor over the serial port (UART).

Wiring: sensor TX -> Pi RXD (GPIO 15), sensor RX -> Pi TXD (GPIO 14),
        VIN -> 5 V, GND -> GND.
The sensor uses 3.3 V levels on TX/RX, which matches the Pi directly.

On the Pi 5 the UART must be enabled first
(see README, section "Raspberry Pi vorbereiten").

Protocol (datasheet):
  We send 9 bytes:      FF 01 86 00 00 00 00 00 79   ("give me the CO2 value")
  The sensor replies:   FF 86 HH LL .. .. .. .. CS
     HH LL = CO2 value in ppm (high byte, low byte)
     CS    = checksum, lets us detect transmission errors

After power-on the sensor needs about 3 minutes of warm-up. Before that it
delivers inaccurate values (usually 400 or 5000 ppm).
"""

import time

import config
from sensors.base import Sensor


class MHZ19CO2(Sensor):
    NAME = "co2"
    COLUMNS = ["co2_ppm"]

    CMD_READ_CO2 = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])
    REPLY_LENGTH = 9

    def __init__(self):
        import serial  # package "pyserial"; imported here for the simulation mode

        # The port is opened ONCE and stays open. (The old code re-opened it
        # for every reading, which is slow and unnecessary.)
        self.port = serial.Serial(
            config.CO2_SERIAL_PORT,
            baudrate=config.CO2_BAUDRATE,
            timeout=1,  # wait at most 1 second for a reply
        )

    def read(self):
        # Throw away old, possibly half replies so we start clean.
        self.port.reset_input_buffer()
        self.port.write(self.CMD_READ_CO2)
        self.port.flush()
        time.sleep(0.1)

        reply = self.port.read(self.REPLY_LENGTH)
        if len(reply) != self.REPLY_LENGTH:
            raise IOError(f"no/incomplete reply ({len(reply)} of 9 bytes)")
        if reply[0] != 0xFF or reply[1] != 0x86:
            raise IOError(f"unexpected reply: {reply.hex(' ')}")
        if self.checksum(reply) != reply[8]:
            raise IOError(f"checksum mismatch: {reply.hex(' ')}")

        co2_ppm = (reply[2] << 8) | reply[3]
        return {"co2_ppm": co2_ppm}

    @staticmethod
    def checksum(packet):
        """
        Checksum as in the datasheet: add bytes 1 to 7, keep the lowest byte,
        invert it bitwise and add 1.
        """
        total = sum(packet[1:8]) & 0xFF
        return ((0xFF - total) + 1) & 0xFF

    def close(self):
        self.port.close()
