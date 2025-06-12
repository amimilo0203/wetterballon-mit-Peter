import smbus2
import time

class GDK101:
    def __init__(self, bus=1, address=0x18):
        self.bus = smbus2.SMBus(bus)
        self.address = address
        self.sensitivity = 8.33  # CPM pro µSv/h

    def read_dose_rate(self):
        try:
            # Lese 2 Bytes von Register 0x00
            data = self.bus.read_i2c_block_data(self.address, 0x00, 2)
            # Kombiniere die beiden Bytes zu einem 16-Bit-Wert
            raw_value = data[0] << 8 | data[1]
            # Konvertiere den Rohwert in µSv/h
            dose_rate = raw_value / 100.0  # Annahme: 100 Einheiten = 1 µSv/h
            return dose_rate
        except Exception as e:
            print(f"Fehler beim Lesen des Sensors: {e}")
            return None

if __name__ == "__main__":
    sensor = GDK101()
    while True:
        dose = sensor.read_dose_rate()
        if dose is not None:
            print(f"Aktuelle Strahlungsdosis: {dose:.2f} µSv/h")
        else:
            print("Fehler beim Auslesen der Strahlungsdosis.")
        time.sleep(5)
