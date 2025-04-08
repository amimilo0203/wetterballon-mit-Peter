import spidev
import time

# Create SPI connection
spi = spidev.SpiDev()
spi.open(0, 0)  # (bus, device)
spi.max_speed_hz = 1350000

def read_channel(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

def convert_voltage(data):
    volts = (data * 3.3) / 1023
    return volts

try:
    while True:
        uv_value = read_channel(0)
        uv_voltage = convert_voltage(uv_value)
        uv_index = uv_voltage / 0.1  # 0.1V per UV index
        
        print(f"UV Voltage: {uv_voltage:.2f}V")
        print(f"UV Index: {uv_index:.1f}")
        print("--------------------")
        time.sleep(1)

except KeyboardInterrupt:
    spi.close()
