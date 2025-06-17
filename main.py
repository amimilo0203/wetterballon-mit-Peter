# Combined Sensor Reader for AS7265X, BME280, HMC5883L, MCP3008 Sensors, and CO2

import time
import math
import struct
from smbus2 import SMBus
from bme280 import BME280
import serial
import spidev


# ==================== AS7265X Spectral Sensor ====================
class AS7265X:
    AS7265X_I2C_ADDR = 0x49
    AS726X_SLAVE_STATUS_REG = 0x00
    AS726X_SLAVE_WRITE_REG = 0x01
    AS726X_SLAVE_READ_REG = 0x02
    AS726X_TX_VALID = 0x02
    AS726X_RX_VALID = 0x01
    AS726X_VIRTUAL_READ = 0x00
    AS726X_LED_CONTROL = 0x07
    AS726X_CONTROL_SETUP = 0x04
    AS726X_DEVICE_SELECT_CONTROL = 0x4F
    DEVICE_MASTER = 0x00
    DEVICE_SECONDARY = 0x01
    DEVICE_TERTIARY = 0x02
    CALIBRATED_DATA_START = 0x14

    def __init__(self, bus=1, address=AS7265X_I2C_ADDR):
        self.bus = SMBus(bus)
        self.address = address

    def _wait_tx_ready(self):
        while self.bus.read_byte_data(self.address, self.AS726X_SLAVE_STATUS_REG) & self.AS726X_TX_VALID:
            pass

    def _wait_rx_ready(self):
        while not self.bus.read_byte_data(self.address, self.AS726X_SLAVE_STATUS_REG) & self.AS726X_RX_VALID:
            pass

    def _read_virtual_register(self, reg):
        self._wait_tx_ready()
        self.bus.write_byte_data(self.address, self.AS726X_SLAVE_WRITE_REG, reg | self.AS726X_VIRTUAL_READ)
        self._wait_rx_ready()
        return self.bus.read_byte_data(self.address, self.AS726X_SLAVE_READ_REG)

    def _write_virtual_register(self, reg, value):
        self._wait_tx_ready()
        self.bus.write_byte_data(self.address, self.AS726X_SLAVE_WRITE_REG, reg | 0x80)
        self._wait_tx_ready()
        self.bus.write_byte_data(self.address, self.AS726X_SLAVE_WRITE_REG, value)

    def set_measurement_mode(self, mode=3):
        val = self._read_virtual_register(self.AS726X_CONTROL_SETUP)
        val = (val & 0b11110011) | (mode << 2)
        self._write_virtual_register(self.AS726X_CONTROL_SETUP, val)

    def enable_led(self, enable=True):
        self._write_virtual_register(self.AS726X_LED_CONTROL, 0x3F if enable else 0x00)

    def software_reset(self):
        self._write_virtual_register(self.AS726X_CONTROL_SETUP, 0x80)
        time.sleep(1)

    def select_device(self, code):
        self._write_virtual_register(self.AS726X_DEVICE_SELECT_CONTROL, code)
        time.sleep(0.1)

    def data_ready(self):
        return bool(self._read_virtual_register(self.AS726X_CONTROL_SETUP) & 0x02)

    def read_calibrated_channels(self):
        raw_bytes = [self._read_virtual_register(reg) for reg in
                     range(self.CALIBRATED_DATA_START, self.CALIBRATED_DATA_START + 24)]
        return [struct.unpack('>f', bytes(raw_bytes[i:i + 4]))[0] for i in range(0, 24, 4)]

    def read_all_18_channels(self):
        full_spectrum = []
        for dev in [self.DEVICE_MASTER, self.DEVICE_SECONDARY, self.DEVICE_TERTIARY]:
            self.select_device(dev)
            self.set_measurement_mode(3)
            time.sleep(0.2)
            while not self.data_ready():
                time.sleep(0.01)
            full_spectrum.extend(self.read_calibrated_channels())
        return full_spectrum


# ==================== SPI ADC Helper ====================
class MCP3008:
    def __init__(self, bus=0, device=0, speed_hz=1350000):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz

    def read_channel(self, channel):
        if not 0 <= channel <= 7:
            return -1
        adc = self.spi.xfer2([1, (8 + channel) << 4, 0])
        return ((adc[1] & 3) << 8) + adc[2]

    def convert_voltage(self, data):
        return (data * 3.3) / 1023


# ==================== HMC5883L Compass ====================
class HMC5883L:
    ADDRESS = 0x1E
    REG = {'CONFIG_A': 0x00, 'CONFIG_B': 0x01, 'MODE': 0x02, 'X_MSB': 0x03, 'Y_MSB': 0x07, 'Z_MSB': 0x05}

    def __init__(self, bus=1):
        self.bus = SMBus(bus)
        self.setup()

    def setup(self):
        self.bus.write_byte_data(self.ADDRESS, self.REG['CONFIG_A'], 0x70)
        self.bus.write_byte_data(self.ADDRESS, self.REG['CONFIG_B'], 0x20)
        self.bus.write_byte_data(self.ADDRESS, self.REG['MODE'], 0x00)

    def read_axis(self, addr):
        high = self.bus.read_byte_data(self.ADDRESS, addr)
        low = self.bus.read_byte_data(self.ADDRESS, addr + 1)
        value = (high << 8) + low
        return value - 65536 if value > 32768 else value

    def get_heading(self):
        x, y = self.read_axis(self.REG['X_MSB']), self.read_axis(self.REG['Y_MSB'])
        heading = math.degrees(math.atan2(y, x)) + 0.22  # Declination
        return heading + 360 if heading < 0 else heading


# ==================== CO2 Sensor ====================
def read_co2():
    try:
        with serial.Serial("/dev/serial0", 9600, timeout=1) as ser:
            ser.write(b"\xFF\x01\x86\x00\x00\x00\x00\x00\x79")
            time.sleep(0.1)
            resp = ser.read(9)
            if len(resp) == 9 and resp[0] == 0xFF and resp[1] == 0x86:
                return (resp[2] << 8) | resp[3]
    except Exception as e:
        print(f"CO2 Error: {e}")
    return None


# ==================== Main Program ====================
def main():
    # Initialize sensors
    spectral = AS7265X()
    spectral.software_reset()
    spectral.enable_led(True)

    bme_bus = SMBus(1)
    bme280 = BME280(i2c_dev=bme_bus)

    compass = HMC5883L()

    adc = MCP3008()

    print("All sensors initialized. Starting measurements...")

    try:
        while True:
            # Read sensors
            spectrum = spectral.read_all_18_channels()
            temp, hum, press = bme280.get_temperature(), bme280.get_humidity(), bme280.get_pressure()
            heading = compass.get_heading()
            uv_raw = adc.read_channel(0)
            mq9_raw = adc.read_channel(4)
            co2 = read_co2()

            # Output results
            print("\n=== Spectral Data ===")
            for i, val in enumerate(spectrum, 1):
                print(f"CH{i:02}: {val:.3f}")

            print("\n=== Environmental ===")
            print(f"Temp: {temp:.2f}°C | Humidity: {hum:.2f}% | Pressure: {press:.2f} hPa")

            print("\n=== Positional ===")
            print(f"Compass: {heading:.1f}°")

            print("\n=== Analog Sensors ===")
            print(f"UV: {adc.convert_voltage(uv_raw):.2f}V | MQ9: {adc.convert_voltage(mq9_raw):.2f}V")

            if co2:
                print(f"CO2: {co2} ppm")

            time.sleep(2)  # Measurement interval

    except KeyboardInterrupt:
        print("\nShutting down...")
        spectral.enable_led(False)
        bme_bus.close()
        adc.spi.close()


if __name__ == "__main__":
    main()