"""
Package "sensors" - one module per sensor.

Every sensor is a class that inherits from Sensor (in base.py) and needs to
provide exactly two things:

    COLUMNS  - list of the column names the sensor delivers
    read()   - returns a dictionary {column_name: value}

That is all you need to know to add a new sensor.
See README, section "Einen neuen Sensor hinzufügen".
"""

from sensors.bme280_environment import BME280Environment
from sensors.as7265x_spectral import AS7265xSpectral
from sensors.hmc5883l_compass import HMC5883LCompass
from sensors.guva_s12sd_uv import GUVAS12SDUltraviolet
from sensors.mq9_gas import MQ9Gas
from sensors.mhz19_co2 import MHZ19CO2
from sensors.gdk101_radiation import GDK101Radiation
from sensors import simulation

# {name: class} for the real hardware. The names are the same as in
# config.ENABLED_SENSORS. The ORDER here is the order of the CSV columns.
REAL_SENSORS = {
    "bme280": BME280Environment,
    "as7265x": AS7265xSpectral,
    "hmc5883l": HMC5883LCompass,
    "uv": GUVAS12SDUltraviolet,
    "mq9": MQ9Gas,
    "co2": MHZ19CO2,
    "radiation": GDK101Radiation,
}

# Same names, but classes that invent plausible values without any hardware.
# Used by `python main.py --simulate` to test the program on a normal PC.
SIMULATED_SENSORS = {
    "bme280": simulation.SimulatedBME280,
    "as7265x": simulation.SimulatedAS7265x,
    "hmc5883l": simulation.SimulatedHMC5883L,
    "uv": simulation.SimulatedUV,
    "mq9": simulation.SimulatedMQ9,
    "co2": simulation.SimulatedCO2,
    "radiation": simulation.SimulatedRadiation,
}
