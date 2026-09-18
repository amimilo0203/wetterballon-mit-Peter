"""
config.py - Every setting of the weather balloon project in ONE place.

If you change something on the hardware (another pin, another I2C address,
another measurement interval), this is the only file you need to touch.
The rest of the code reads its settings from here.

Tip: after editing, run `python main.py --simulate --once` to check that the
file still has no syntax errors.
"""

# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

# Seconds between two measurements.
MEASUREMENT_INTERVAL_S = 2

# Which sensors are connected. A sensor set to False is ignored completely
# (no columns in the CSV file, no error messages).
ENABLED_SENSORS = {
    "bme280": True,      # temperature, humidity, pressure (I2C)
    "as7265x": True,     # 18-channel spectral sensor (I2C)
    "hmc5883l": True,    # magnetometer / compass (I2C)
    "uv": True,          # GUVA-S12SD UV sensor (analog, via MCP3008)
    "mq9": True,         # MQ-9 gas sensor (analog, via MCP3008)
    "co2": True,         # MH-Z19 CO2 sensor (serial port / UART)
    "radiation": True,   # GDK101 gamma radiation sensor (I2C)
}

# If a sensor is not found at start-up (loose cable, ...) or fails repeatedly,
# the program tries to restart it every this many seconds.
SENSOR_RETRY_INTERVAL_S = 60

# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------

# The measurements are written into these directories. EVERY directory that
# exists (or can be created) gets its own copy. That way you can additionally
# save to a USB stick: if the stick is missing, that directory is skipped and
# the program keeps running.
#
# Relative paths (like "data") are relative to the project folder.
LOG_DIRECTORIES = [
    "data",
    # "/media/pi/USBSTICK/weather-balloon",   # example for a second copy
]

# Files are then called data/flight_0001.csv, data/flight_0002.csv, ...
# Every program start (also after a power cut) creates a NEW file with the next
# free number. Old files are never overwritten.
LOG_FILE_PREFIX = "flight"

# ---------------------------------------------------------------------------
# Connections (buses, addresses, channels)
# ---------------------------------------------------------------------------

# The Raspberry Pi's I2C bus on GPIO 2 (SDA) / GPIO 3 (SCL) is bus 1.
I2C_BUS = 1

# I2C addresses. Run `i2cdetect -y 1` to see what is connected.
I2C_ADDR_BME280 = 0x76      # some modules use 0x77
I2C_ADDR_AS7265X = 0x49
I2C_ADDR_HMC5883L = 0x1E
I2C_ADDR_GDK101 = 0x18

# SPI for the MCP3008 analog-to-digital converter (bus 0, chip select CE0 = GPIO 8).
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 1_350_000

# Which MCP3008 inputs (CH0 - CH7) the analog sensors are wired to.
ADC_CHANNEL_UV = 0
ADC_CHANNEL_MQ9 = 4

# Reference voltage of the MCP3008 (VREF pin). Normally 3.3 V on the Pi.
ADC_REFERENCE_VOLTAGE_V = 3.3

# Serial port for the CO2 sensor (GPIO 14 = TXD, GPIO 15 = RXD).
CO2_SERIAL_PORT = "/dev/serial0"
CO2_BAUDRATE = 9600

# ---------------------------------------------------------------------------
# Sensor details
# ---------------------------------------------------------------------------

# Should the built-in LEDs of the spectral sensor be switched on?
# For measuring sun/sky light: False (otherwise you measure your own LED).
# For measuring surfaces right in front of the sensor: True.
# (In the original code the LEDs were switched on.)
AS7265X_LEDS_ON = False

# Magnetic declination at the launch site in degrees (east = positive).
# Germany in 2026: roughly +3 to +5 degrees. Look it up for your location at
# https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml
MAGNETIC_DECLINATION_DEG = 4.0

# ---------------------------------------------------------------------------
# Display (optional)
# ---------------------------------------------------------------------------

# A small OLED display (SH1107, 128x64, I2C) shows the current values.
# Set to False if no display is connected. Logging works without a display.
DISPLAY_ENABLED = False
I2C_ADDR_DISPLAY = 0x3C
