import serial
import time


def read_co2():
    # Öffne die serielle Verbindung zum Sensor
    ser = serial.Serial("/dev/serial0", baudrate=9600, timeout=1)

    # Sende Befehl zum Anfordern der CO2-Konzentration
    command = b"\xFF\x01\x86\x00\x00\x00\x00\x00\x79"
    ser.write(command)
    time.sleep(0.1)

    # Lese die Antwort vom Sensor
    response = ser.read(9)

    if len(response) == 9 and response[0] == 0xFF and response[1] == 0x86:
        high_byte = response[2]
        low_byte = response[3]
        co2_concentration = (high_byte << 8) | low_byte
        print(f"CO2-Konzentration: {co2_concentration} ppm")
    else:
        print("Fehler beim Lesen der Daten")

    ser.close()


if __name__ == "__main__":
    while True:
        read_co2()
        time.sleep(2)  # Alle 2 Sekunden auslesen
