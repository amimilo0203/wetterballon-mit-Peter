from smbus2 import SMBus
import time
import struct

AS7265X_I2C_ADDR = 0x49

# Virtual register interface
AS726X_SLAVE_STATUS_REG = 0x00
AS726X_SLAVE_WRITE_REG = 0x01
AS726X_SLAVE_READ_REG = 0x02

AS726X_TX_VALID = 0x02
AS726X_RX_VALID = 0x01

AS726X_VIRTUAL_WRITE = 0x80
AS726X_VIRTUAL_READ = 0x00

AS726X_LED_CONTROL = 0x07
AS726X_CONTROL_SETUP = 0x04
AS726X_DEVICE_SELECT_CONTROL = 0x4F

# Sensor bank codes
DEVICE_MASTER = 0x00  # AS72651
DEVICE_SECONDARY = 0x01  # AS72652
DEVICE_TERTIARY = 0x02  # AS72653

# Data start for calibrated float values
CALIBRATED_DATA_START = 0x14  # Registers 0x14 to 0x25 (6 float values)

class AS7265x:
    def __init__(self, bus=1, address=AS7265X_I2C_ADDR):
        self.bus = SMBus(bus)
        self.address = address

    def _read_virtual_register(self, reg):
        # Wait until TX buffer is ready
        while True:
            status = self.bus.read_byte_data(self.address, AS726X_SLAVE_STATUS_REG)
            if not (status & AS726X_TX_VALID):
                break
        self.bus.write_byte_data(self.address, AS726X_SLAVE_WRITE_REG, reg | AS726X_VIRTUAL_READ)
        # Wait for RX valid
        while True:
            status = self.bus.read_byte_data(self.address, AS726X_SLAVE_STATUS_REG)
            if status & AS726X_RX_VALID:
                break
        return self.bus.read_byte_data(self.address, AS726X_SLAVE_READ_REG)

    def _write_virtual_register(self, reg, value):
        while True:
            status = self.bus.read_byte_data(self.address, AS726X_SLAVE_STATUS_REG)
            if not (status & AS726X_TX_VALID):
                break
        self.bus.write_byte_data(self.address, AS726X_SLAVE_WRITE_REG, reg | AS726X_VIRTUAL_WRITE)
        while True:
            status = self.bus.read_byte_data(self.address, AS726X_SLAVE_STATUS_REG)
            if not (status & AS726X_TX_VALID):
                break
        self.bus.write_byte_data(self.address, AS726X_SLAVE_WRITE_REG, value)

    def set_measurement_mode(self, mode=3):
        val = self._read_virtual_register(AS726X_CONTROL_SETUP)
        val = (val & 0b11110011) | (mode << 2)
        self._write_virtual_register(AS726X_CONTROL_SETUP, val)

    def enable_led(self, enable=True):
        val = 0x3F if enable else 0x00
        self._write_virtual_register(AS726X_LED_CONTROL, val)

    def software_reset(self):
        self._write_virtual_register(AS726X_CONTROL_SETUP, 0x80)
        time.sleep(1)

    def select_device(self, code):
        self._write_virtual_register(AS726X_DEVICE_SELECT_CONTROL, code)
        time.sleep(0.1)

    def data_ready(self):
        status = self._read_virtual_register(AS726X_CONTROL_SETUP)
        return bool(status & 0x02)

    def read_calibrated_channels(self):
        # Read 6 channels, each a 4-byte float split across 2 registers each
        raw_bytes = []
        for reg in range(CALIBRATED_DATA_START, CALIBRATED_DATA_START + 24):
            byte = self._read_virtual_register(reg)
            raw_bytes.append(byte)
        # Convert every 4 bytes to a float
        floats = []
        for i in range(0, 24, 4):
            f = struct.unpack('>f', bytes(raw_bytes[i:i+4]))[0]  # Big-endian float
            floats.append(f)
        return floats

    def read_all_18_channels(self):
        full_spectrum = []
        for dev in [DEVICE_MASTER, DEVICE_SECONDARY, DEVICE_TERTIARY]:
            self.select_device(dev)
            self.set_measurement_mode(3)  # Continuous mode
            time.sleep(0.2)
            while not self.data_ready():
                time.sleep(0.01)
            values = self.read_calibrated_channels()
            full_spectrum.extend(values)
        return full_spectrum

# Main program
if __name__ == "__main__":
    sensor = AS7265x()
    print("Initializing AS7265x...")
    sensor.software_reset()
    sensor.enable_led(True)

    try:
        while True:
            spectrum = sensor.read_all_18_channels()
            print("Spectral Values (18 channels):")
            for i, val in enumerate(spectrum, 1):
                print(f"  CH{i:02}: {val:.3f}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sensor.enable_led(False)
