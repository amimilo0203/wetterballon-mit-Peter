"""
display.py - Optional small OLED display (SH1107, 128x64 pixels, I2C 0x3C).

Shows the most important current values so you can check the sensors in the
field without a laptop. Uses the "luma.oled" library.

The display is optional: if config.DISPLAY_ENABLED is False, or the library
is missing, or the display is not connected, the program simply runs without
it. Logging is never affected by display problems.
"""

import config


class Display:
    def __init__(self):
        from luma.core.interface.serial import i2c
        from luma.core.render import canvas
        from luma.oled.device import sh1107

        self._canvas = canvas
        serial = i2c(port=config.I2C_BUS, address=config.I2C_ADDR_DISPLAY)
        self.device = sh1107(serial, width=128, height=64)

    def show(self, values, errors):
        """Draws up to 5 lines with the most important values."""
        lines = [
            _line("T", values.get("temperature_c"), "C", "H", values.get("humidity_pct"), "%"),
            _line("P", values.get("pressure_hpa"), "hPa"),
            _line("CO2", values.get("co2_ppm"), "ppm", "UV", values.get("uv_index"), ""),
            _line("Rad", values.get("radiation_1min_usvh"), "uSv/h"),
            f"errors: {len(errors)}" if errors else "all sensors ok",
        ]
        with self._canvas(self.device) as draw:
            for i, text in enumerate(lines):
                draw.text((0, i * 12), text, fill=255)

    def show_message(self, text):
        with self._canvas(self.device) as draw:
            draw.text((0, 0), text, fill=255)

    def close(self):
        try:
            self.device.cleanup()
        except Exception:
            pass


def _line(label1, value1, unit1, label2=None, value2=None, unit2=""):
    """Formats 'T 21.3C  H 45%' style lines; missing values show as '--'."""
    text = f"{label1} {_fmt(value1)}{unit1}"
    if label2 is not None:
        text += f"  {label2} {_fmt(value2)}{unit2}"
    return text


def _fmt(value):
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)
