import spidev
import time

# SPI-Objekt initialisieren
spi = spidev.SpiDev()
spi.open(0, 0)  # SPI Bus 0, Chip Select 0
spi.max_speed_hz = 1350000  # Optimierte SPI-Geschwindigkeit für MCP3008


# Funktion zum Auslesen des ADC-Wertes (MCP3008)
def read_adc():
    channel = 0  # Fix auf A0

    # SPI-Daten senden und empfangen
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    raw_value = ((adc[1] & 3) << 8) + adc[2]  # 10-Bit ADC-Wert auslesen
    return raw_value


# Funktion zur Umrechnung des ADC-Werts in eine Spannung
# 3.3V ist die Referenzspannung des Raspberry Pi
def convert_to_voltage(adc_value, v_ref=3.3):
    return (adc_value / 1023.0) * v_ref


# Funktion zur Umrechnung der Spannung in die UV-Intensität
# Kalibrierung erforderlich - Beispielwerte verwendet
def calculate_uv_intensity(voltage):
    return voltage * 10  # Beispielumrechnung: 1V = 10 mW/cm² (Anpassen nach Datenblatt)


# Hauptprogramm
def main():
    print("GUVA-S12D Sensor - UV-Messung starten:")
    try:
        while True:
            adc_value = read_adc()  # A0 des MCP3008 auslesen
            voltage = convert_to_voltage(adc_value)
            uv_intensity = calculate_uv_intensity(voltage)

            print(f"ADC Wert: {adc_value} -> Spannung: {voltage:.2f} V -> UV Intensität: {uv_intensity:.2f} mW/cm²")
            time.sleep(2)  # Messung alle 2 Sekunden

    except KeyboardInterrupt:
        print("Programm beendet.")
        spi.close()


if __name__ == "__main__":
    main()
