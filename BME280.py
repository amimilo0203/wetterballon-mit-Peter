import smbus2
import time
from bme280 import BME280

# Initialisiere den I2C-Bus
bus = smbus2.SMBus(1)
sensor = BME280(i2c_dev=bus)

try:
    while True:
        temperature = sensor.get_temperature()
        pressure = sensor.get_pressure()
        humidity = sensor.get_humidity()

        print(f"Temperatur: {temperature:.2f} °C")
        print(f"Luftdruck: {pressure:.2f} hPa")
        print(f"Luftfeuchtigkeit: {humidity:.2f} %")
        print("--------------------------")

        time.sleep(2)  # 2 Sekunden warten
except KeyboardInterrupt:
    print("Messung beendet.")
