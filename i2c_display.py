import time
import Adafruit_CharLCD as LCD

# Initialisiere das Display (Adresse und Pins entsprechend anpassen)
lcd = LCD.Adafruit_CharLCD(0x27, 2, 1, 0, 4, 5, 6, 7, 3)

# Gebe "Hallo" auf dem Display aus
lcd.message('Hallo')

# Warte 5 Sekunden und lösche dann das Display
time.sleep(5)
lcd.clear()
