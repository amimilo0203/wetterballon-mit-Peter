import RPi.GPIO as GPIO
import time
from datetime import datetime

# Konfiguration
GPIO.setmode(GPIO.BCM)
GEIGER_PIN = 17  # GPIO 17 (Pin 11)
GPIO.setup(GEIGER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Zählervariablen
impulse = 0
startzeit = time.time()

# Kalibrierungskonstante
# Für den SEN0463: 151 CPM ≈ 1 µSv/h
CPM_PRO_USV = 151.0

def impuls_erkannt(channel):
    global impulse
    impulse += 1

# Ereignis-Callback einrichten
GPIO.add_event_detect(GEIGER_PIN, GPIO.FALLING, callback=impuls_erkannt)

print("Geigerzähler gestartet. Drücke Strg+C zum Beenden.")

try:
    while True:
        time.sleep(60)  # Warte 60 Sekunden
        dauer = time.time() - startzeit
        cpm = impulse / dauer * 60  # Impulse pro Minute
        usv = cpm / CPM_PRO_USV
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] CPM: {cpm:.2f} | Dosis: {usv:.4f} µSv/h")
        impulse = 0
        startzeit = time.time()
except KeyboardInterrupt:
    print("Beende das Programm...")
finally:
    GPIO.cleanup()
