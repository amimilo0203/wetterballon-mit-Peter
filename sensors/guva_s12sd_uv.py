"""
guva_s12sd_uv.py - GUVA-S12SD: UV sensor (analog, via the MCP3008).

The sensor outputs a voltage that rises with the UV radiation.
Wiring: OUT -> MCP3008 channel config.ADC_CHANNEL_UV, VCC -> 3.3 V, GND -> GND.

Rule of thumb from the manufacturer: UV index = voltage / 0.1 V.
This is a rough approximation (not a calibrated measurement), but good enough
to see how the UV level changes with altitude.
"""

import config
from sensors.base import Sensor
from sensors.mcp3008_adc import MCP3008


class GUVAS12SDUltraviolet(Sensor):
    NAME = "uv"
    COLUMNS = ["uv_voltage_v", "uv_index"]

    VOLTS_PER_UV_INDEX = 0.1

    def __init__(self):
        self.adc = MCP3008()
        self.channel = config.ADC_CHANNEL_UV

    def read(self):
        voltage = self.adc.read_voltage(self.channel)
        return {
            "uv_voltage_v": round(voltage, 3),
            "uv_index": round(voltage / self.VOLTS_PER_UV_INDEX, 1),
        }

    def close(self):
        self.adc.close()
