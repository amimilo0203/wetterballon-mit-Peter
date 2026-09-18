"""
mcp3008_adc.py - MCP3008: analog-to-digital converter with 8 inputs (SPI).

The Raspberry Pi has no analog inputs. Sensors that only output a voltage
(UV sensor, MQ-9 gas sensor) are therefore connected to the MCP3008. It
converts the voltage into a number from 0 to 1023 (10 bit) that we fetch
over SPI.

Wiring:  CLK -> GPIO 11 (SCLK), DOUT -> GPIO 9 (MISO), DIN -> GPIO 10 (MOSI),
         CS  -> GPIO 8 (CE0),   VDD + VREF -> 3.3 V,    AGND + DGND -> GND.

This file is NOT a sensor in the sense of base.py but a helper class used by
guva_s12sd_uv.py and mq9_gas.py.
"""

import config


class MCP3008:
    """Reads raw values and voltages from the 8 channels of the MCP3008."""

    MAX_RAW = 1023  # 10 bit -> 0 ... 1023

    def __init__(self):
        import spidev  # import here so the simulation mode works without spidev

        self.spi = spidev.SpiDev()
        self.spi.open(config.SPI_BUS, config.SPI_DEVICE)
        self.spi.max_speed_hz = config.SPI_SPEED_HZ
        self.spi.mode = 0

    def read_raw(self, channel):
        """Returns the raw value (0 - 1023) of channel 0 - 7."""
        if not 0 <= channel <= 7:
            raise ValueError(f"MCP3008 only has channels 0-7, not {channel}")

        # The MCP3008 protocol (datasheet, section 6.1):
        #   byte 1: start bit                -> 0b00000001
        #   byte 2: "single-ended" + channel -> (8 + channel) << 4
        #   byte 3: don't care, only clocks  -> 0
        # Reply: the lowest 2 bits of byte 2 plus all of byte 3 form the 10 bits.
        reply = self.spi.xfer2([1, (8 + channel) << 4, 0])
        return ((reply[1] & 0b11) << 8) | reply[2]

    def read_voltage(self, channel):
        """Returns the measured voltage in volts."""
        return self.raw_to_voltage(self.read_raw(channel))

    @staticmethod
    def raw_to_voltage(raw):
        return raw * config.ADC_REFERENCE_VOLTAGE_V / MCP3008.MAX_RAW

    def close(self):
        self.spi.close()
