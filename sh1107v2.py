from luma.core.interface.serial import i2c
from luma.oled.device import sh1107
from luma.core.render import canvas
from PIL import ImageFont

# I2C-Schnittstelle initialisieren (Standard-Adresse 0x3C)
serial = i2c(port=1, address=0x3C)

# SH1107 Display mit 128x64 Pixel initialisieren
device = sh1107(serial_interface=serial, width=128, height=64)

# Schriftart laden (Fallback auf Default, falls DejaVu nicht da ist)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except:
    from PIL import ImageFont
    font = ImageFont.load_default()

# Text anzeigen
with canvas(device) as draw:
    draw.text((10, 25), "Hello World", font=font, fill=255)
