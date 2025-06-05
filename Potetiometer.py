   import time
   import board
   import busio
   import digitalio
   import adafruit_mcp3008

   # Use the board.SPI() object to create the SPI bus
   spi = busio.SPI(board.SCK, board.MISO, board.MOSI)

   # Create the MCP3008 object
   cs_pin = digitalio.DigitalInOut(board.D25) # Configure the chip select pin
   mcp3008 = adafruit_mcp3008.MCP3008(spi=spi, cs=cs_pin)

   # Select the channel to read from the potentiometer
   channel = 0

   # Read the value from the channel
   try:
       while True:
           value = mcp3008.read_analog_value(channel)
           print(f"Potentiometer value: {value}")
           time.sleep(0.1)
   except KeyboardInterrupt:
       print("Exiting...")
