"""
mq9_gas.py - MQ-9: gas sensor for carbon monoxide (CO) and flammable gases
             (analog, via the MCP3008).

Wiring: A0 -> MCP3008 channel config.ADC_CHANNEL_MQ9, VCC -> 5 V (heater!),
        GND -> GND.
CAUTION: the sensor has a heater and needs 5 V. Its output can rise above
3.3 V. A voltage divider in front of the MCP3008 input is required,
otherwise the MCP3008 gets damaged.

What we store: only the raw value and the voltage. Converting to ppm is not
possible in a meaningful way without calibrating with known gases. For us,
the change over the flight is interesting, not the absolute value.

Note: after power-on the heater needs several minutes until the readings
are stable. Treat the first minutes with care.
"""

import config
from sensors.base import Sensor
from sensors.mcp3008_adc import MCP3008


class MQ9Gas(Sensor):
    NAME = "mq9"
    COLUMNS = ["mq9_raw", "mq9_voltage_v"]

    def __init__(self):
        self.adc = MCP3008()
        self.channel = config.ADC_CHANNEL_MQ9

    def read(self):
        raw = self.adc.read_raw(self.channel)
        return {
            "mq9_raw": raw,
            "mq9_voltage_v": round(self.adc.raw_to_voltage(raw), 3),
        }

    def close(self):
        self.adc.close()
