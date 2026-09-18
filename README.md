# Wetterballon mit Peter

Messdatenlogger für einen Wetterballon auf Basis eines **Raspberry Pi 5**.
Das Programm liest alle paar Sekunden sämtliche Sensoren aus und speichert die
Werte so, dass sie auch einen **Stromausfall** überleben. Nach dem Flug erzeugt
ein Auswertungsskript Diagramme und ein interaktives Dashboard.

Der Code ist bewusst für Einsteiger geschrieben: Jede Datei hat oben eine
Erklärung, jeder Sensor ist ein eigenes kleines Modul, und alle Einstellungen
stehen in einer einzigen Datei (`config.py`). Bezeichner und Kommentare im
Code sind Englisch, diese Anleitung ist Deutsch.

---

## Inhalt

1. [Was das Projekt macht](#1-was-das-projekt-macht)
2. [Projektstruktur](#2-projektstruktur)
3. [Schnellstart](#3-schnellstart)
4. [Verkabelung](#4-verkabelung)
5. [Konfiguration](#5-konfiguration)
6. [So läuft eine Messung ab](#6-so-läuft-eine-messung-ab)
7. [Datenspeicherung: Warum die Daten einen Stromausfall überleben](#7-datenspeicherung-warum-die-daten-einen-stromausfall-überleben)
8. [Datenformat der CSV-Dateien](#8-datenformat-der-csv-dateien)
9. [Werkzeuge](#9-werkzeuge)
10. [Auswertung: Plots und Dashboard](#10-auswertung-plots-und-dashboard)
11. [Einen neuen Sensor hinzufügen](#11-einen-neuen-sensor-hinzufügen)
12. [Fehlersuche](#12-fehlersuche)
13. [Vorgehen beim Umbau (Dokumentation)](#13-vorgehen-beim-umbau-dokumentation)

---

## 1. Was das Projekt macht

Alle `MEASUREMENT_INTERVAL_S` Sekunden (Standard: 2) passiert Folgendes:

1. Jeder Sensor wird einmal ausgelesen.
2. Alle Werte landen als **eine Zeile** in einer CSV-Datei (`data/flight_0001.csv`).
3. Die Zeile wird sofort physisch auf die SD-Karte geschrieben (nicht nur in einen Zwischenspeicher).
4. Optional zeigt ein kleines OLED-Display die wichtigsten Werte.

Ein Sensor, der ausfällt, stört die anderen nicht. Fällt der Strom aus, startet
das Programm beim nächsten Einschalten automatisch wieder und schreibt in eine
neue Datei weiter.

### Sensoren

| Name in `config.py` | Sensor | Misst | Anschluss | Modul |
|---|---|---|---|---|
| `bme280` | BME280 | Temperatur, Luftfeuchte, Luftdruck | I2C `0x76` | `sensors/bme280_environment.py` |
| `as7265x` | AS7265x (SparkFun Triad) | Lichtspektrum, 18 Wellenlängen 410–940 nm | I2C `0x49` | `sensors/as7265x_spectral.py` |
| `hmc5883l` | HMC5883L | Magnetfeld X/Y/Z, Kompassrichtung | I2C `0x1E` | `sensors/hmc5883l_compass.py` |
| `uv` | GUVA-S12SD | UV-Strahlung (UV-Index) | analog, MCP3008 Kanal 0 | `sensors/guva_s12sd_uv.py` |
| `mq9` | MQ-9 | Kohlenmonoxid / brennbare Gase (Rohwert) | analog, MCP3008 Kanal 4 | `sensors/mq9_gas.py` |
| `co2` | MH-Z19 | CO₂-Konzentration | UART `/dev/serial0` | `sensors/mhz19_co2.py` |
| `radiation` | FTLAB GDK101 | Gammastrahlung (µSv/h) | I2C `0x18`, **5 V** | `sensors/gdk101_radiation.py` |
| – | MCP3008 | Analog-Digital-Wandler für `uv` und `mq9` | SPI CE0 | `sensors/mcp3008_adc.py` |
| – | SH1107 OLED (optional) | Anzeige | I2C `0x3C` | `display.py` |

---

## 2. Projektstruktur

```
wetterballon-mit-Peter/
├── README.md                  diese Anleitung
├── config.py                  ALLE Einstellungen (Pins, Adressen, Intervall, Ordner)
├── main.py                    das Hauptprogramm, das auf dem Ballon läuft
├── data_logger.py             stromausfallsicheres Schreiben der CSV-Dateien
├── display.py                 optionales OLED-Display
├── sensors/                   ein Modul pro Sensor
│   ├── __init__.py            Liste aller Sensoren (echt + simuliert)
│   ├── base.py                gemeinsame Basisklasse "Sensor"
│   ├── bme280_environment.py  Temperatur / Luftfeuchte / Luftdruck
│   ├── as7265x_spectral.py    Spektralsensor
│   ├── hmc5883l_compass.py    Magnetometer / Kompass
│   ├── mcp3008_adc.py         Analog-Digital-Wandler (Hilfsklasse)
│   ├── guva_s12sd_uv.py       UV-Sensor
│   ├── mq9_gas.py             Gassensor
│   ├── mhz19_co2.py           CO₂-Sensor
│   ├── gdk101_radiation.py    Strahlungssensor
│   └── simulation.py          erfundene Werte zum Testen ohne Hardware
├── tools/
│   ├── test_sensor.py         einen einzelnen Sensor ausprobieren
│   ├── live_view.py           aktuelle Werte im Terminal mitverfolgen
│   └── merge_logs.py          alle CSV-Dateien zu einer zusammenfügen
├── analysis/
│   ├── flight_data.py         CSV-Dateien einlesen (auch mit kaputten Zeilen)
│   └── analyze.py             Diagramme + Dashboard erzeugen
├── install.sh                 Einrichtung auf dem Raspberry Pi (einmalig)
├── weather-balloon.service    systemd-Dienst: Autostart + automatischer Neustart
├── requirements.txt           Python-Pakete für den Pi
├── requirements-analysis.txt  Python-Pakete für die Auswertung (Laptop)
├── data/                      hier landen die Messdaten (wird automatisch angelegt)
└── analysis_output/           hier landen Dashboard und Plots (wird automatisch angelegt)
```

---

## 3. Schnellstart

### 3.1 Ohne Hardware am PC ausprobieren (Simulation)

Das Programm hat einen Simulationsmodus mit erfundenen, aber realistischen
Werten (Aufstieg bis ca. 30 km, Platzen, Abstieg). So kann man Logging und
Auswertung testen, bevor der Pi überhaupt verkabelt ist.

```bash
python main.py --simulate --verbose
```

Stoppen mit `Strg+C`. Die Daten liegen danach in `data/flight_0001.csv`.
Einen ganzen Flug in wenigen Sekunden erzeugen:

```bash
python main.py --simulate --interval 0 --max-measurements 400
```

Dann die Auswertung starten (siehe [Abschnitt 10](#10-auswertung-plots-und-dashboard)).

### 3.2 Auf dem Raspberry Pi 5 einrichten

Voraussetzung: Raspberry Pi OS (Bookworm oder neuer), Internet für die Installation.

```bash
cd ~
git clone https://github.com/amimilo0203/wetterballon-mit-Peter
cd wetterballon-mit-Peter
bash install.sh
sudo reboot
```

`install.sh` macht Folgendes (jeder Schritt steht kommentiert im Skript):

1. installiert Systempakete (`python3-venv`, `i2c-tools`, …)
2. schaltet I2C, SPI und die UART-Schnittstelle ein und die serielle Konsole aus
3. fügt deinen Benutzer den Gruppen `i2c`, `spi`, `dialout`, `gpio` hinzu
4. legt eine virtuelle Python-Umgebung `venv/` an und installiert `requirements.txt`
5. installiert den systemd-Dienst `weather-balloon` und aktiviert den Autostart

Nach dem Neustart läuft der Logger automatisch. Prüfen:

```bash
sudo systemctl status weather-balloon
```

```bash
python tools/live_view.py
```

Zum manuellen Testen den Dienst stoppen und das Programm direkt starten:

```bash
sudo systemctl stop weather-balloon
./venv/bin/python main.py --verbose
```

### 3.3 Checkliste vor dem Start

- [ ] `i2cdetect -y 1` zeigt `0x18`, `0x1e`, `0x49`, `0x76` (und `0x3c`, falls Display)
- [ ] `python tools/test_sensor.py <name>` liefert für jeden Sensor plausible Werte
- [ ] `sudo systemctl status weather-balloon` meldet `active (running)`
- [ ] `python tools/live_view.py` zeigt aktuelle Zeilen, `errors: none`
- [ ] Stecker ziehen, wieder einstecken: nach dem Booten entsteht `flight_000N+1.csv` und der Logger läuft weiter
- [ ] CO₂- und MQ-9-Sensor mindestens 3 Minuten vorwärmen lassen
- [ ] Uhrzeit stimmt (`date`), siehe [Uhrzeit](#uhrzeit)
- [ ] Genug freier Platz: `df -h` (ein Tag Messungen sind etwa 20 MB)

---

## 4. Verkabelung

Alle I2C-Sensoren hängen parallel an denselben zwei Leitungen.

| Pi-Pin (BCM) | Funktion | Verbunden mit |
|---|---|---|
| GPIO 2 | I2C SDA | BME280, AS7265x, HMC5883L, GDK101, Display |
| GPIO 3 | I2C SCL | BME280, AS7265x, HMC5883L, GDK101, Display |
| GPIO 8 | SPI CE0 | MCP3008 CS |
| GPIO 9 | SPI MISO | MCP3008 DOUT |
| GPIO 10 | SPI MOSI | MCP3008 DIN |
| GPIO 11 | SPI SCLK | MCP3008 CLK |
| GPIO 14 | UART TXD | MH-Z19 RX |
| GPIO 15 | UART RXD | MH-Z19 TX |
| 3,3 V | Versorgung | BME280, AS7265x, HMC5883L, Display, MCP3008 (VDD **und** VREF), GUVA-S12SD |
| 5 V | Versorgung | MH-Z19, MQ-9 (Heizung), GDK101 |
| GND | Masse | alles |

MCP3008: `CH0` → UV-Sensor, `CH4` → MQ-9.

**Achtung GDK101:** Der Strahlungssensor braucht laut Datenblatt 4,0–6,0 V, also
den 5-V-Pin. Mit 3,3 V läuft er nicht zuverlässig. Seine Datenleitungen arbeiten
mit 3,3 V und dürfen direkt an GPIO 2/3. Seine I2C-Adresse (Standard `0x18`)
wird über die Lötbrücken A0/A1 eingestellt und nur beim Einschalten gelesen.
Der I2C-Bus muss auf den Standard-100 kHz bleiben; `i2c_arm_baudrate=400000`
verträgt dieser Sensor nicht.

**Achtung MQ-9:** Der Sensor läuft mit 5 V und sein Ausgang kann über 3,3 V
steigen. Vor den MCP3008-Eingang gehört ein Spannungsteiler (z. B. 10 kΩ / 20 kΩ),
sonst wird der Wandler beschädigt.

**Achtung Pi 5:** Die alte Bibliothek `RPi.GPIO` funktioniert auf dem Pi 5 nicht
mehr. Dieses Projekt benutzt deshalb nur `smbus2` (I2C), `spidev` (SPI) und
`pyserial` (UART), die weiterhin funktionieren.

---

## 5. Konfiguration

Alles Einstellbare steht in [`config.py`](config.py), mit Kommentar bei jedem Wert.
Die wichtigsten:

| Einstellung | Bedeutung |
|---|---|
| `MEASUREMENT_INTERVAL_S` | Sekunden zwischen zwei Messungen |
| `ENABLED_SENSORS` | welche Sensoren angeschlossen sind (`True` / `False`) |
| `LOG_DIRECTORIES` | in welche Ordner geschrieben wird (mehrere möglich, z. B. zusätzlich USB-Stick) |
| `I2C_ADDR_*` | I2C-Adressen, falls ein Modul eine andere Adresse hat |
| `ADC_CHANNEL_UV`, `ADC_CHANNEL_MQ9` | an welchem MCP3008-Eingang die Analogsensoren hängen |
| `AS7265X_LEDS_ON` | LEDs des Spektralsensors an/aus (für Himmelslicht: aus) |
| `MAGNETIC_DECLINATION_DEG` | Missweisung am Startort für die Kompassrichtung |
| `DISPLAY_ENABLED` | OLED-Display benutzen |

Nach jeder Änderung kurz prüfen, ob die Datei noch fehlerfrei ist:

```bash
python main.py --simulate --once
```

---

## 6. So läuft eine Messung ab

[`main.py`](main.py) ist absichtlich kurz gehalten. Der Ablauf:

```
Start
 ├─ Ereignisprotokoll öffnen            (data/events.log)
 ├─ jeden aktivierten Sensor starten    (Fehler -> wird später erneut versucht)
 ├─ DataLogger öffnen                   (neue Datei data/flight_NNNN.csv)
 ├─ Display starten (optional)
 └─ Schleife:
      ├─ alle Sensoren lesen  -> values (was geklappt hat), errors (was nicht)
      ├─ eine Zeile schreiben -> sofort auf die SD-Karte (fsync)
      ├─ Display aktualisieren
      └─ warten bis zur nächsten Messung
```

Wichtige Verhaltensregeln, die in `SensorManager` (in `main.py`) stecken:

- Ein Sensor, der beim Start fehlt, wird alle `SENSOR_RETRY_INTERVAL_S` Sekunden erneut gestartet.
- Ein Sensor, der 5-mal hintereinander beim Lesen scheitert, wird neu gestartet.
- Jeder Fehler wird mit Grund in die Spalte `errors` der CSV-Zeile geschrieben, und die anderen Sensoren werden trotzdem gemessen.
- `Strg+C` oder `systemctl stop` beenden die laufende Messung sauber und schließen alle Dateien.

Jeder Sensor ist eine Klasse mit nur zwei Pflichtteilen (siehe [`sensors/base.py`](sensors/base.py)):

```python
class BME280Environment(Sensor):
    NAME = "bme280"
    COLUMNS = ["temperature_c", "humidity_pct", "pressure_hpa"]

    def read(self):
        return {"temperature_c": ..., "humidity_pct": ..., "pressure_hpa": ...}
```

---

## 7. Datenspeicherung: Warum die Daten einen Stromausfall überleben

### Das Problem

Wenn ein Programm in eine Datei schreibt, landen die Daten zuerst in einem
Zwischenspeicher im Arbeitsspeicher. Linux schreibt sie erst Sekunden bis
Minuten später auf die SD-Karte. Fällt in dieser Zeit der Strom aus (leerer
Akku, Wackelkontakt beim Aufprall), sind diese Messwerte verloren. Beim
klassischen `print()` in eine Datei oder `csv.writer` ohne weitere Maßnahmen
kann so leicht der interessanteste Teil des Flugs fehlen.

### Die Maßnahmen (alle in [`data_logger.py`](data_logger.py))

| Maßnahme | Was sie bewirkt |
|---|---|
| `flush()` + `os.fsync()` nach **jeder** Zeile | Die Zeile ist danach garantiert physisch auf der Karte. Nur die allerletzte, gerade in Arbeit befindliche Zeile kann verloren gehen. |
| `fsync` auch auf das Verzeichnis | Sonst könnte die neue Datei nach dem Stromausfall im Ordner "unsichtbar" sein. |
| Neue Datei bei **jedem** Programmstart (`flight_0001.csv`, `flight_0002.csv`, …) | Es wird nie eine bestehende Datei geöffnet oder überschrieben (Öffnen im Modus `"x"`). Ein Neustart nach Stromausfall ist an der Dateinummer erkennbar. |
| Mehrere Zielordner (`LOG_DIRECTORIES`) | Jede Zeile wird z. B. auf SD-Karte **und** USB-Stick geschrieben. Fällt ein Ziel aus, laufen die anderen weiter; ausgefallene Ziele werden alle 30 s erneut probiert. |
| Schreibfehler werden abgefangen | Eine volle Karte oder ein abgezogener Stick beenden das Programm nicht. |
| Ereignisprotokoll `events.log` | Start, Sensorausfälle und Neustarts stehen mit Uhrzeit in einer zweiten Datei, ebenfalls mit `fsync`. |
| systemd-Dienst mit `Restart=always` | Nach Stromausfall oder Absturz startet das Programm von selbst wieder, ohne dass jemand eingreifen muss. `StartLimitIntervalSec=0` verhindert, dass systemd nach mehreren Abstürzen aufgibt. |
| Kaputte Zeilen werden beim Einlesen erkannt | `analysis/flight_data.py` überspringt und zählt abgeschnittene Zeilen, statt abzustürzen. |

### Was bei einem Stromausfall konkret passiert

1. Strom weg um 11:42:13. Die Zeile von 11:42:12 ist bereits sicher auf der Karte.
   Höchstens die Zeile, die gerade geschrieben wurde, ist abgeschnitten.
2. Strom wieder da. Der Pi bootet (ca. 30–60 s), systemd startet `main.py`.
3. `main.py` legt `flight_0002.csv` an und misst weiter. In `events.log` steht
   `=== program start ===` mit Uhrzeit.
4. Nach dem Flug: `python analysis/analyze.py` liest beide Dateien, überspringt
   die abgeschnittene Zeile und zeigt im Dashboard `Restarts: 1`.

### Empfehlungen für den Flug

- **Zweite Kopie auf einen USB-Stick:** Stick einstecken, mounten lassen und den
  Pfad in `LOG_DIRECTORIES` eintragen. SD-Karten sind beim Stromausfall das
  empfindlichste Bauteil; eine zweite Kopie auf einem anderen Medium ist die
  wirksamste Versicherung.
- **Gute SD-Karte** (Markenkarte, A1/A2-Klasse) und vorher einmal komplett beschreiben/testen.
- **RTC-Batterie:** Der Pi 5 hat eine eingebaute Echtzeituhr, aber nur mit
  angeschlossener Pufferbatterie läuft sie ohne Strom weiter. Ohne Batterie
  und ohne Netz stimmt nach einem Neustart die Uhrzeit nicht (siehe Uhrzeit).
- **Sauber herunterfahren, wenn möglich:** `sudo shutdown -h now`, bevor man den
  Akku abklemmt. Nötig ist es dank fsync nicht, aber es schont die Karte.
- **Hardware-Watchdog (optional):** In `/etc/systemd/system.conf` die Zeile
  `RuntimeWatchdogSec=15` aktivieren, dann startet der Pi automatisch neu,
  falls das ganze System einfriert.

### Uhrzeit

Die Spalte `time` ist die Uhrzeit des Pi. Ohne Internet und ohne RTC-Batterie
ist sie nach einem Neustart falsch (der Pi übernimmt dann die zuletzt
gespeicherte Zeit). Deshalb gibt es zusätzlich:

- `uptime_s`: Sekunden seit Programmstart, unabhängig von der Uhr, immer korrekt.
- `measurement_no`: fortlaufende Nummer innerhalb der Datei.

Vor dem Start die Uhr stellen, indem der Pi kurz ins WLAN/Handy-Hotspot geht,
oder manuell: `sudo date -s "2026-09-18 10:00:00"`.

---

## 8. Datenformat der CSV-Dateien

Komma-getrennt, UTF-8, erste Zeile = Spaltennamen. Fehlende Werte (Sensor
ausgefallen) sind leere Zellen. Öffnen mit Excel, LibreOffice oder pandas.

| Spalte | Einheit | Woher |
|---|---|---|
| `time` | Datum/Uhrzeit ISO 8601 | Logger |
| `uptime_s` | s seit Programmstart | Logger |
| `measurement_no` | – | Logger |
| `temperature_c` | °C | BME280 |
| `humidity_pct` | % relative Feuchte | BME280 |
| `pressure_hpa` | hPa | BME280 |
| `spectrum_410nm` … `spectrum_940nm` (18 Spalten) | µW/cm² | AS7265x |
| `mag_x_ut`, `mag_y_ut`, `mag_z_ut` | µT | HMC5883L |
| `heading_deg` | ° (0 = Nord, 90 = Ost) | HMC5883L |
| `uv_voltage_v` | V | GUVA-S12SD |
| `uv_index` | – (Näherung: V / 0,1) | GUVA-S12SD |
| `mq9_raw` | 0–1023 (Rohwert) | MQ-9 |
| `mq9_voltage_v` | V | MQ-9 |
| `co2_ppm` | ppm | MH-Z19 |
| `radiation_10min_usvh` | µSv/h (10-Minuten-Mittel) | GDK101 |
| `radiation_1min_usvh` | µSv/h (1-Minuten-Mittel, verrauscht) | GDK101 |
| `radiation_uptime_min` | min seit Sensorstart | GDK101 |
| `radiation_status` | 0 = gerade eingeschaltet, 1 = < 10 min, 2 = eingelaufen | GDK101 |
| `radiation_vibration` | 1 = Erschütterung, Messung gestört | GDK101 |
| `errors` | Text, z. B. `co2: checksum mismatch` | Logger |

Datenmenge: eine Zeile hat rund 220 Zeichen. Bei 2 s Intervall sind das etwa
0,4 MB pro Stunde bzw. 10 MB pro Tag.

---

## 9. Werkzeuge

Alle Werkzeuge werden aus dem Projektordner gestartet.

| Befehl | Zweck |
|---|---|
| `python tools/test_sensor.py --list` | zeigt alle Sensornamen und ihre Spalten |
| `python tools/test_sensor.py bme280` | liest einen Sensor jede Sekunde; Fehler werden angezeigt statt abzustürzen (Kabel wackeln und zuschauen) |
| `python tools/live_view.py` | zeigt die letzte Zeile der neuesten Datei, alle 2 s aktualisiert; warnt, wenn die Daten älter als 30 s sind |
| `python tools/merge_logs.py` | fügt alle `flight_*.csv` zu `data/merged.csv` zusammen, mit Spalten `file` und `restart_no` |
| `python main.py --simulate` | Hauptprogramm mit erfundenen Werten |
| `python main.py --once --verbose` | genau eine Messung, dann Ende (Schnelltest auf dem Pi) |

Alle Werkzeuge akzeptieren `--help`.

---

## 10. Auswertung: Plots und Dashboard

Die Auswertung läuft am besten am Laptop (geht aber auch auf dem Pi).
Einmalig die Pakete installieren:

```bash
pip install -r requirements-analysis.txt
```

Dann (Datenordner vom Pi kopieren, z. B. per `scp` oder USB-Stick):

```bash
python analysis/analyze.py --data data
```

Ergebnis in `analysis_output/`:

| Datei | Inhalt |
|---|---|
| `dashboard.html` | **Interaktives Dashboard** – im Browser öffnen. Kennzahlen oben, alle Diagramme (zoomen durch Ziehen, Werte beim Überfahren), Tabellen zur Sensorverfügbarkeit, den Dateien und allen Min/Max/Mittelwerten. Funktioniert ohne Internet (plotly.js ist eingebettet, daher ca. 5 MB). Mit `--cdn` wird die Datei klein, braucht dann aber Internet zum Anzeigen. |
| `plots/*.png` | dieselben Diagramme als Bilder für Berichte und Präsentationen (`--no-png` überspringt sie) |
| `summary.csv` | Min / Max / Mittelwert / erster / letzter Wert jeder Spalte |

### Was das Dashboard zeigt

- **Kennzahlen:** Flugdauer, Anzahl Messungen, Neustarts, vollständige Zeilen,
  maximale Höhe (geschätzt), minimaler Druck, minimale Temperatur, maximaler
  UV-Index, maximale Strahlung, CO₂.
- **Flugprofil:** geschätzte Höhe und Luftdruck über der Zeit.
- **Atmosphäre:** Temperatur, Luftfeuchte, CO₂.
- **Strahlung:** UV-Index, Gammastrahlung (1-min und 10-min-Mittel).
- **Gas und Orientierung:** MQ-9, Kompassrichtung, Magnetfeld.
- **Lichtspektrum:** Heatmap aller 18 Wellenlängen über die Zeit und das
  mittlere Spektrum des Flugs.
- **Vertikalprofile:** Temperatur, Strahlung und UV gegen die Höhe, getrennt
  nach Aufstieg und Abstieg – die klassischen Ballon-Diagramme.
- **Datenqualität:** Fehlerquote pro Sensor und über die Zeit.

Unter jedem Diagramm steht ein Satz, worauf man achten sollte.

### Höhe aus dem Luftdruck

Es gibt keinen GPS-Empfänger, deshalb wird die Höhe aus dem Luftdruck mit der
barometrischen Höhenformel der Standardatmosphäre geschätzt
(`pressure_to_altitude` in `analyze.py`). Das ist auf einige hundert Meter
genau. **Wichtig:** Der BME280 ist nur für 300–1100 hPa spezifiziert, also bis
etwa 9 km Höhe. Darüber werden Druck und damit die geschätzte Höhe zunehmend
unzuverlässig. Wetterballons steigen oft 25–35 km hoch. Wer die Höhe wirklich
wissen will, braucht einen GPS-Empfänger, der auch über 18 km funktioniert
(viele Module hören dort aus Exportgründen auf).

### Diagramme anpassen

Alle Diagramme sind in `analysis/analyze.py` in **einer Liste** beschrieben
(`chart_specs`). Ein neues Zeitdiagramm ist ein Eintrag wie:

```python
dict(kind="lines", section="Atmosphere", title="Relative humidity", unit="%",
     columns=["humidity_pct"], labels=["humidity"], note="Was man sehen sollte."),
```

Die Farben stammen aus einer farbenblind-sicheren Palette; pro Diagramm gibt
es nur eine Achse (keine Doppelachsen), damit nichts fehlinterpretiert wird.

---

## 11. Einen neuen Sensor hinzufügen

1. Neue Datei `sensors/<name>_<was>.py` anlegen. Vorlage: `sensors/mq9_gas.py`
   (analog) oder `sensors/hmc5883l_compass.py` (I2C).
2. Eine Klasse schreiben, die von `Sensor` erbt, mit `NAME`, `COLUMNS` und `read()`.
   Hardware-Bibliotheken im `__init__` importieren (damit die Simulation ohne
   sie auskommt). Warteschleifen immer mit `wait_until(...)` und Zeitlimit.
3. In `sensors/__init__.py` importieren und in `REAL_SENSORS` eintragen.
4. Optional: eine simulierte Variante in `sensors/simulation.py` schreiben und
   in `SIMULATED_SENSORS` eintragen (sonst schlägt `--simulate` für diesen Namen fehl).
5. In `config.py` unter `ENABLED_SENSORS` den Namen mit `True` eintragen.
6. Testen: `python tools/test_sensor.py <name>`.
7. Optional: in `analysis/analyze.py` bei `chart_specs` ein Diagramm und bei
   `SENSOR_COLUMNS` die Spalte für die Verfügbarkeitsstatistik ergänzen.

Die CSV-Spalten des neuen Sensors erscheinen automatisch.

---

## 12. Fehlersuche

| Symptom | Ursache / Lösung |
|---|---|
| `sensor 'xyz' NOT available: [Errno 121] Remote I/O error` | I2C-Gerät antwortet nicht: Verkabelung, `i2cdetect -y 1`, Adresse in `config.py`. |
| `i2cdetect` zeigt `0x0d` statt `0x1e` | Das "HMC5883L"-Modul ist in Wahrheit ein QMC5883L. Der braucht einen anderen Treiber (andere Register). |
| `Permission denied: '/dev/i2c-1'` o. ä. | Benutzer nicht in der Gruppe `i2c`/`spi`/`dialout`. `install.sh` erledigt das; danach neu anmelden. |
| `co2: no/incomplete reply (0 of 9 bytes)` | UART nicht freigeschaltet (`dtparam=uart0=on` in `/boot/firmware/config.txt`), serielle Konsole noch aktiv, oder TX/RX vertauscht. |
| CO₂ dauerhaft 400 oder 5000 ppm | Sensor noch nicht warm (3 Minuten) oder Versorgung zu schwach (5 V, > 150 mA). |
| `as7265x: Timeout (1.0 s) while waiting for ...` | Sensor hängt oder schlechte Verbindung. Pull-ups prüfen, Kabel kürzen, `I2C_ADDR_AS7265X` prüfen. |
| `radiation` liefert nur 0 | Normal am Anfang. Die Spalte `radiation_status` zeigt es: 0 = gerade eingeschaltet, 1 = noch keine 10 Minuten, 2 = eingelaufen. Erst ab 2 sind die Werte belastbar. |
| `radiation: no answer from the GDK101` | Sensor hängt an 3,3 V statt 5 V, falsche Adresse (A0/A1-Brücken), oder er ist noch keine 10 s mit Strom versorgt. `i2cdetect -y 1` muss `0x18` zeigen. |
| `radiation_vibration` fast immer 1 | Der Sensor blendet bei Erschütterungen etwa eine halbe Sekunde aus. Modul auf Schaumstoff entkoppeln, schwarzen Schwamm auf der Platinenrückseite dranlassen. |
| Spektralsensor zeigt fast nur Rauschen | LEDs aus? Sensor mit Sicht nach oben montieren; bei direkter Sonne kann er übersteuern. |
| `Could not write to ANY of the log directories` | Alle Ordner in `LOG_DIRECTORIES` sind nicht beschreibbar (Rechte, Karte voll, Stick nicht gemountet). |
| Dienst startet ständig neu (`journalctl -u weather-balloon`) | Python-Fehler beim Start, z. B. Tippfehler in `config.py`. `./venv/bin/python main.py --once` von Hand ausführen und die Meldung lesen. |
| `ModuleNotFoundError: No module named 'smbus2'` | Nicht die venv benutzt. `./venv/bin/python main.py` statt `python main.py`, oder `source venv/bin/activate`. |
| `externally-managed-environment` bei `pip install` | Bookworm erlaubt kein systemweites pip. Immer in der venv installieren (`./venv/bin/pip`). |

Live-Ausgabe des Dienstes:

```bash
journalctl -u weather-balloon -f
```

---

## 13. Vorgehen beim Umbau (Dokumentation)

Dieser Abschnitt beschreibt, was beim Refactoring gemacht wurde und warum.

### 13.1 Ausgangslage

Das Repository bestand aus 13 einzelnen Skripten: pro Sensor ein Testskript
(teils Deutsch, teils Englisch, teils aus Foren kopiert), dazu `main.py`, das
alle Sensoren kombinierte und die Werte nur auf den Bildschirm ausgab. Es gab
keine Speicherung der Messwerte, keine Fehlerbehandlung und keinen Autostart.

### 13.2 Analyse des alten Codes

Beim Durchlesen sind diese Probleme aufgefallen und wurden behoben:

| Alte Datei | Problem | Lösung |
|---|---|---|
| `main.py` | Werte wurden nur ausgegeben, nicht gespeichert | `data_logger.py` |
| `main.py` | Ein Fehler in irgendeinem Sensor beendete das Programm | jeder Sensor einzeln abgesichert (`SensorManager`) |
| `main.py`, `as7265x.py` | `while True:`-Warteschleifen ohne Zeitlimit: bei einem Wackelkontakt fror das ganze Programm für immer ein | `wait_until()` mit Timeout in `sensors/base.py` |
| `main.py` (HMC5883L) | Missweisung `0.22` wurde in Grad addiert, war aber in `magnetometer.py` als Bogenmaß gemeint (≈ 12,6°); außerdem konnte der Kurs > 360° werden | Deklination in Grad in `config.py`, Ergebnis `% 360` |
| `magnetometer.py` | Zweierkomplement mit `> 32768` statt `>= 32768`; Rohwerte als "µT" ausgegeben | korrekte Umrechnung, echte µT über Verstärkungsfaktor 1090 LSB/Gauss |
| `radiation_GDK101.py` | las Register `0x00` und teilte durch 100 – der GDK101 hat gar keine Register, sondern beantwortet Ein-Byte-Befehle; der Wert war bedeutungslos | Befehle laut Datenblatt (siehe 13.3), Format Ganzzahl + Hundertstel |
| `CO2.py`, `main.py` | serieller Port wurde bei jeder Messung neu geöffnet; Prüfsumme der Antwort wurde nicht kontrolliert | Port bleibt offen, Prüfsumme wird geprüft, Eingangspuffer wird vor jeder Anfrage geleert |
| `main.py`, `as7265x.py` | Messmodus 3 als "continuous" kommentiert, laut Datenblatt ist es "one-shot"; Modus wurde pro Chip neu gesetzt | ein One-Shot pro Messung, dann alle drei Chips lesen; Kanäle mit Wellenlänge statt `CH01…CH18` benannt |
| `main.py`, `as7265x.py` | LEDs mit `0x3F` (100 mA) eingeschaltet – für Himmelslicht-Messungen unpassend | `AS7265X_LEDS_ON` in `config.py`, Standard aus, sonst 12,5 mA |
| `spi_comm_mcp3008.py` | benutzt `RPi.GPIO`, das auf dem Pi 5 nicht läuft; Bit-Banging statt SPI | entfernt, `spidev` in `mcp3008_adc.py` |
| `sh1107 demo v319 i2c 128x64.py` | MicroPython-Code (`machine.Pin`), läuft auf keinem Raspberry Pi | entfernt |
| `bme280v2.py` | kein gültiges Python (vermutlich aus einem Screenshot abgetippt) | entfernt; BME280 in `bme280_environment.py` mit Pimoroni-Bibliothek |
| `Potetiometer.py` | Einrückung fehlerhaft (Datei startet mit Leerzeichen), andere Bibliothek als der Rest | entfernt (war nur ein ADC-Test) |
| `i2c_display.py` | Test für ein anderes Display (Zeichen-LCD), das nicht mehr verwendet wird | entfernt |
| `Guva-s12dv2.py`, `MQ9.py` | jeweils eigene SPI-Initialisierung, Duplikate von `main.py` | ein gemeinsamer `MCP3008` |

Die alten Dateien sind in der Git-Historie erhalten (Commit `7bab540` und
davor): `git show 7bab540:CO2.py`.

### 13.3 Prüfung gegen die Datenblätter

Nach dem Umbau wurden die Treiber gegen die Hersteller-Datenblätter gegengeprüft.
Für den **GDK101** ist diese Prüfung abgeschlossen und hat einen schweren Fehler
aufgedeckt, der auch in meiner ersten Fassung steckte: Die Befehlsnummern waren
um eine Stelle verschoben. Richtig sind laut FTLAB-Datenblatt v1.5:

| Befehl | Bedeutung | Antwort (2 Bytes) |
|---|---|---|
| `0xA0` | Reset | 1 = ok, 0 = fehlgeschlagen |
| `0xB0` | Status | Byte 0: 0 / 1 / 2 (siehe `radiation_status`), Byte 1: Erschütterung |
| `0xB1` | Messdauer | Minuten, Sekunden |
| `0xB2` | Dosisleistung, 10-Minuten-Mittel | Ganzzahl, Hundertstel |
| `0xB3` | Dosisleistung, 1-Minuten-Mittel | Ganzzahl, Hundertstel |
| `0xB4` | Firmware-Version | Haupt-, Unterversion |

Mit der falschen Zuordnung hätte die Spalte `radiation_10min_usvh` in Wahrheit
den Status enthalten und `radiation_1min_usvh` die Messdauer – der Fehler wäre
in den Diagrammen kaum aufgefallen. Daraus wurden zusätzlich abgeleitet:

- Jede Antwort wird jetzt auf Plausibilität geprüft (Hundertstel ≤ 99,
  Dosis ≤ 200 µSv/h, Status ∈ {0,1,2}). Genau diese Prüfung hätte den Fehler
  sofort sichtbar gemacht.
- Beim Start wird bis zu zwölfmal im Sekundentakt nachgefragt, weil der Sensor
  nach dem Einschalten rund 10 Sekunden braucht, bevor er antwortet.
- Zwei neue Spalten: `radiation_status` und `radiation_vibration`. Die
  Erschütterungserkennung ist beim schaukelnden Ballon wichtig, weil der Sensor
  bei einem Stoß etwa eine halbe Sekunde lang nicht misst.
- Versorgung korrigiert: 4,0–6,0 V, also 5 V statt der zuvor dokumentierten 3,3 V.
- Die Bezeichnung „DFRobot SEN0463“ war falsch. Das ist ein anderes Produkt
  (Geiger-Müller-Röhre mit Impulsausgang, kein I2C). Falls auf dem Ballon
  tatsächlich dieses Modul steckt, zeigt `i2cdetect -y 1` keine `0x18` und es
  braucht einen anderen Treiber, der GPIO-Impulse zählt.
- Für die Auswertung gilt: Bei etwa 12 Impulsen pro Minute und µSv/h ist der
  1-Minuten-Wert stark verrauscht. Die Höhenprofile benutzen deshalb den
  10-Minuten-Mittelwert.

Die Prüfung der übrigen Sensoren (AS7265x, MH-Z19, HMC5883L, BME280, MCP3008)
sowie der Raspberry-Pi-5-Einrichtung wurde begonnen, aber nicht abgeschlossen.
Diese Treiber beruhen auf Datenblättern und bekannten Bibliotheken, sind aber
nicht gegengeprüft. Wer sie anfasst, sollte dasselbe Vorgehen wählen:
Befehlsnummern, Byte-Reihenfolge und Wertebereiche einzeln nachschlagen und
eine Plausibilitätsprüfung einbauen.

### 13.4 Entscheidungen

- **Ein Modul pro Sensor, eine gemeinsame Basisklasse.** Jede Datei ist kurz,
  hat oben eine Erklärung mit Anschlussbelegung und ist unabhängig testbar.
- **Alle Einstellungen in `config.py`.** Nichts ist mehr im Code versteckt.
- **Simulationsmodus.** Das Programm läuft ohne Hardware auf jedem PC; so
  konnten Logger, Hauptprogramm und Auswertung hier vollständig getestet werden.
- **Englische Bezeichner**, deutsche Anleitung – auf Wunsch des Teams.
- **CSV statt Datenbank.** Einfach, robust, überall lesbar, eine Zeile pro Messung
  lässt sich atomar sichern.
- **Fehler werden protokolliert, nicht verschluckt.** Jede Zeile hat eine Spalte
  `errors`, es gibt `events.log`, und alle Werkzeuge zeigen Fehler an.
- **Keine Doppelachsen in den Diagrammen** und eine geprüfte, farbenblind-sichere
  Palette, damit die Auswertung nicht in die Irre führt.

### 13.5 Was getestet wurde – und was nicht

Getestet (auf dem Entwicklungsrechner, ohne Sensoren):

- Simulation kompletter Flüge inkl. simulierter Sensorausfälle
- Logger: neue Datei pro Start, `fsync`, mehrere Verzeichnisse, abgeschnittene Zeile
- `merge_logs.py`, `live_view.py`, `analyze.py` (Dashboard + 17 PNG-Diagramme)
- Dashboard im Browser, auch auf Handybreite

**Nicht** getestet, weil keine Hardware vorlag: die echten Sensortreiber. Die
Logik wurde gegen Datenblätter und bekannte Bibliotheken (SparkFun AS7265x,
DFRobot GDK101, Winsen MH-Z19, Honeywell HMC5883L, Pimoroni BME280) geprüft, aber
erst `python tools/test_sensor.py <name>` auf dem Pi zeigt, ob alles stimmt.
Empfohlene Reihenfolge auf dem Pi: `bme280` → `uv` / `mq9` → `hmc5883l` →
`co2` → `radiation` → `as7265x` (der komplizierteste).

### 13.6 Offene Punkte / Ideen

- GPS-Modul für echte Höhe und Position (und zum Wiederfinden).
- Der BME280 reicht nur bis ca. 9 km – für Druck in größerer Höhe wäre ein
  MS5611 oder ein Sensor mit größerem Bereich besser; die Temperatur unter
  −40 °C liegt außerhalb seiner Spezifikation.
- Kalibrierung des MQ-9 mit Referenzgas, wenn absolute Werte gewünscht sind.
- Eine Sicherung auf einen USB-Stick in `LOG_DIRECTORIES` eintragen.
