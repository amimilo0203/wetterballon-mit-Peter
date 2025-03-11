import time
import spidev

# SPI-Setup
spi = spidev.SpiDev()
spi.open(0, 0)  # Bus 0, Device 0
spi.max_speed_hz = 1350000


def read_adc(channel):
    """Liest einen Wert vom MCP3008 ADC ein."""
    if channel < 0 or channel > 7:
        return -1

    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data


def main():
    try:
        while True:
            mq9_value = read_adc(4)  # MQ-9 an Kanal 4
            voltage = (mq9_value * 3.3) / 1023  # Umrechnung in Spannung (bei 3.3V Referenz)
            print(f"MQ-9 ADC-Wert: {mq9_value}, Spannung: {voltage:.2f}V")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMessung beendet.")
        spi.close()


if __name__ == "__main__":
    main()
