import time
import board
import busio
import adafruit_bme280

# Initialisiere den I2C-Bus
i2c = busio.I2C(board.SCL, board.SDA)

# Initialisiere den BME280 Sensor
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

# Setze die Messungs-Überprüfungsrate (default ist 2 Sekunden)
bme280.sea_level_pressure = 1013.25

while True:
    print("\nTemperatur: %0.1f C" % bme280.temperature)
    print("Luftfeuchtigkeit: %0.1f %%" % bme280.humidity)
    print("Luftdruck: %0.1f hPa" % bme280.pressure)
    time.sleep(2)
