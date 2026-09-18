"""
simulation.py - Fake sensors for testing WITHOUT any hardware.

Start the program with `python main.py --simulate` and it uses these classes
instead of the real ones. They invent plausible values for a whole balloon
flight (climb to ~30 km, burst, descent), so you can test the logging and the
analysis tools on a normal PC.

Every simulated class inherits from the real class, so the COLUMNS are
guaranteed to be identical to the real sensor. Only __init__ and read() are
replaced. About 1 in 100 readings deliberately fails, so you can see how
errors show up in the CSV file.
"""

import math
import random

from sensors.as7265x_spectral import AS7265xSpectral
from sensors.bme280_environment import BME280Environment
from sensors.gdk101_radiation import GDK101Radiation
from sensors.guva_s12sd_uv import GUVAS12SDUltraviolet
from sensors.hmc5883l_compass import HMC5883LCompass
from sensors.mhz19_co2 import MHZ19CO2
from sensors.mq9_gas import MQ9Gas

# Every read() advances the simulated flight by this many seconds. With 30,
# a measurement every 2 seconds simulates a flight 15 times faster than real.
SECONDS_PER_READING = 30

# Simulated flight profile
CLIMB_RATE_M_S = 5.0
BURST_ALTITUDE_M = 30_000
DESCENT_RATE_M_S = 8.0
FAILURE_PROBABILITY = 0.01


class FlightModel:
    """A tiny model of the balloon flight shared by all simulated sensors."""

    def __init__(self):
        self.flight_time_s = 0.0

    def advance(self):
        self.flight_time_s += SECONDS_PER_READING

    def altitude_m(self):
        climb_duration = BURST_ALTITUDE_M / CLIMB_RATE_M_S
        if self.flight_time_s <= climb_duration:
            return CLIMB_RATE_M_S * self.flight_time_s
        descent = (self.flight_time_s - climb_duration) * DESCENT_RATE_M_S
        return max(0.0, BURST_ALTITUDE_M - descent)

    def pressure_hpa(self):
        # Barometric formula (international standard atmosphere, simplified)
        h = self.altitude_m()
        return 1013.25 * math.exp(-h / 7400)

    def temperature_c(self):
        # Colder up to the tropopause (~11 km), then slightly warmer again
        h = self.altitude_m()
        if h < 11_000:
            return 15 - 6.5 * h / 1000
        return -56.5 + 1.0 * (h - 11_000) / 1000


# One shared flight model for all simulated sensors. The BME280 (created
# first) is the one that advances the clock, all others only look at it.
FLIGHT = FlightModel()


def _maybe_fail(name):
    if random.random() < FAILURE_PROBABILITY:
        raise IOError(f"simulated {name} read error")


def _noise(scale):
    return random.gauss(0, scale)


class SimulatedBME280(BME280Environment):
    def __init__(self):
        pass  # no hardware to open

    def read(self):
        FLIGHT.advance()
        _maybe_fail(self.NAME)
        humidity = max(1.0, 60 - FLIGHT.altitude_m() / 400 + _noise(2))
        return {
            "temperature_c": round(FLIGHT.temperature_c() + _noise(0.3), 2),
            "humidity_pct": round(humidity, 2),
            "pressure_hpa": round(FLIGHT.pressure_hpa() + _noise(0.5), 2),
        }


class SimulatedAS7265x(AS7265xSpectral):
    def __init__(self):
        pass

    def read(self):
        _maybe_fail(self.NAME)
        # Brighter with altitude (less atmosphere), sun-like spectrum
        brightness = 30 + FLIGHT.altitude_m() / 1000
        values = {}
        for nm in self.ALL_WAVELENGTHS_NM:
            spectral_shape = math.exp(-((nm - 550) / 250) ** 2)
            values[f"spectrum_{nm}nm"] = round(brightness * spectral_shape + abs(_noise(0.5)), 3)
        return values


class SimulatedHMC5883L(HMC5883LCompass):
    def __init__(self):
        pass

    def read(self):
        _maybe_fail(self.NAME)
        # The balloon slowly spins: one turn every 3 minutes
        angle = math.radians((FLIGHT.flight_time_s / 180 * 360) % 360)
        x = 20 * math.cos(angle) + _noise(0.5)
        y = 20 * math.sin(angle) + _noise(0.5)
        return {
            "mag_x_ut": round(x, 2),
            "mag_y_ut": round(y, 2),
            "mag_z_ut": round(-43 + _noise(0.5), 2),
            "heading_deg": round(math.degrees(math.atan2(y, x)) % 360, 1),
        }


class SimulatedUV(GUVAS12SDUltraviolet):
    def __init__(self):
        pass

    def read(self):
        _maybe_fail(self.NAME)
        voltage = min(1.1, 0.25 + FLIGHT.altitude_m() / 40_000 + _noise(0.01))
        return {
            "uv_voltage_v": round(voltage, 3),
            "uv_index": round(voltage / self.VOLTS_PER_UV_INDEX, 1),
        }


class SimulatedMQ9(MQ9Gas):
    def __init__(self):
        pass

    def read(self):
        _maybe_fail(self.NAME)
        raw = int(max(0, min(1023, 300 - FLIGHT.altitude_m() / 150 + _noise(5))))
        return {"mq9_raw": raw, "mq9_voltage_v": round(raw * 3.3 / 1023, 3)}


class SimulatedCO2(MHZ19CO2):
    def __init__(self):
        pass

    def read(self):
        _maybe_fail(self.NAME)
        return {"co2_ppm": int(420 + _noise(8))}


class SimulatedRadiation(GDK101Radiation):
    def __init__(self):
        self.firmware = "sim"

    def read(self):
        _maybe_fail(self.NAME)
        # Cosmic radiation rises with altitude, strongest around 20 km
        h = FLIGHT.altitude_m()
        dose = 0.1 + 3.0 * math.exp(-((h - 20_000) / 9_000) ** 2)
        minutes = FLIGHT.flight_time_s / 60
        return {
            "radiation_10min_usvh": round(dose + abs(_noise(0.02)), 2),
            "radiation_1min_usvh": round(dose + abs(_noise(0.08)), 2),
            "radiation_uptime_min": round(minutes, 1),
            # 0 for the first 10 s, 1 until 10 minutes, then 2
            "radiation_status": 0 if minutes < 1 / 6 else (1 if minutes < 10 else 2),
            # the payload swings, so shocks happen now and then
            "radiation_vibration": 1 if random.random() < 0.1 else 0,
        }
