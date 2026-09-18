"""
main.py - The program that runs on the balloon.

What it does, in one sentence: every few seconds it reads all sensors and
writes one row into a CSV file in a way that survives power cuts.

Usage:
    python main.py                      normal operation on the Raspberry Pi
    python main.py --simulate           fake sensors, works on any PC
    python main.py --once               one measurement, then exit (for testing)
    python main.py --verbose            print every measurement to the screen
    python main.py --interval 0.5       override the interval from config.py

The flow:
    1. open the event log and start every enabled sensor
    2. open the data logger (one new CSV file per program start)
    3. loop forever: read all sensors -> write one row -> update display -> wait
    4. a sensor that fails is retried regularly and never stops the others
    5. on Ctrl+C or a stop signal from systemd, everything is closed cleanly

If the power fails, none of this matters: the rows already written are safe
on the SD card (see data_logger.py), and systemd restarts this program on
the next boot (see README).
"""

import argparse
import signal
import sys
import time

import config
from data_logger import DataLogger, EventLog
from sensors import REAL_SENSORS, SIMULATED_SENSORS

# After this many failed readings in a row, a sensor is restarted.
FAILURES_BEFORE_RESTART = 5

# Without --verbose, print a short status line every N measurements.
STATUS_EVERY_N_MEASUREMENTS = 30


class SensorManager:
    """
    Keeps track of all enabled sensors: starts them, reads them, restarts the
    ones that fail. One failing sensor never affects the others.
    """

    def __init__(self, sensor_classes, events):
        self.sensor_classes = sensor_classes
        self.events = events
        self.sensors = {}          # name -> Sensor object, or None if not working
        self.failures = {}         # name -> number of failed readings in a row
        self.last_attempt = {}     # name -> monotonic time of the last start attempt

        for name in self.enabled_names():
            self.sensors[name] = None
            self.failures[name] = 0
            self.last_attempt[name] = 0.0
            self.start_sensor(name)

    @staticmethod
    def enabled_names():
        return [name for name, enabled in config.ENABLED_SENSORS.items() if enabled]

    def columns(self):
        """All CSV columns of the enabled sensors, in a fixed order."""
        result = []
        for name in self.enabled_names():
            result.extend(self.sensor_classes[name].COLUMNS)
        return result

    def start_sensor(self, name):
        self.last_attempt[name] = time.monotonic()
        self.close_sensor(name)
        try:
            self.sensors[name] = self.sensor_classes[name]()
            self.failures[name] = 0
            self.events.log(f"sensor '{name}' started")
        except Exception as e:
            self.sensors[name] = None
            self.events.log(f"sensor '{name}' NOT available: {e}")

    def close_sensor(self, name):
        sensor = self.sensors.get(name)
        if sensor is not None:
            try:
                sensor.close()
            except Exception:
                pass
        self.sensors[name] = None

    def read_all(self):
        """
        Reads every sensor once. Returns (values, errors):
          values - {column: value} of everything that worked
          errors - ["name: reason", ...] of everything that did not
        """
        values = {}
        errors = []
        for name, sensor in self.sensors.items():
            if sensor is None:
                errors.append(f"{name}: not connected")
                self._maybe_restart(name)
                continue
            try:
                values.update(sensor.read())
                self.failures[name] = 0
            except Exception as e:
                self.failures[name] += 1
                errors.append(f"{name}: {e}")
                if self.failures[name] == FAILURES_BEFORE_RESTART:
                    self.events.log(f"sensor '{name}' failed {FAILURES_BEFORE_RESTART}x in a row: {e}")
                if self.failures[name] >= FAILURES_BEFORE_RESTART:
                    self._maybe_restart(name)
        return values, errors

    def _maybe_restart(self, name):
        waited = time.monotonic() - self.last_attempt[name]
        if waited >= config.SENSOR_RETRY_INTERVAL_S:
            self.events.log(f"trying to restart sensor '{name}'")
            self.start_sensor(name)

    def close_all(self):
        for name in list(self.sensors):
            self.close_sensor(name)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Weather balloon sensor logger")
    parser.add_argument("--simulate", action="store_true",
                        help="use fake sensors (no hardware needed)")
    parser.add_argument("--once", action="store_true",
                        help="take one measurement and exit")
    parser.add_argument("--verbose", action="store_true",
                        help="print every measurement")
    parser.add_argument("--interval", type=float, default=config.MEASUREMENT_INTERVAL_S,
                        help=f"seconds between measurements (default {config.MEASUREMENT_INTERVAL_S})")
    parser.add_argument("--max-measurements", type=int, default=None,
                        help="stop after this many measurements (default: run forever)")
    return parser.parse_args()


def start_display(events):
    """Returns a Display object, or None if the display is disabled or missing."""
    if not config.DISPLAY_ENABLED:
        return None
    try:
        from display import Display
        display = Display()
        display.show_message("weather balloon\nstarting ...")
        events.log("display started")
        return display
    except Exception as e:
        events.log(f"display NOT available, continuing without it: {e}")
        return None


def format_status(values, errors):
    """One short line for the screen, e.g. 'T=21.3C P=1012.1hPa CO2=430ppm errors=0'."""
    parts = []
    if "temperature_c" in values:
        parts.append(f"T={values['temperature_c']}C")
    if "pressure_hpa" in values:
        parts.append(f"P={values['pressure_hpa']}hPa")
    if "co2_ppm" in values:
        parts.append(f"CO2={values['co2_ppm']}ppm")
    if "uv_index" in values:
        parts.append(f"UV={values['uv_index']}")
    if "radiation_1min_usvh" in values:
        parts.append(f"rad={values['radiation_1min_usvh']}uSv/h")
    parts.append(f"errors={len(errors)}")
    return " ".join(parts)


def main():
    args = parse_arguments()

    # A stop request (Ctrl+C or `systemctl stop`) only sets this flag; the
    # loop then finishes the current measurement and closes everything.
    stop_requested = {"value": False}

    def request_stop(signal_number, frame):
        stop_requested["value"] = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    events = EventLog(config.LOG_DIRECTORIES[0])
    events.log("=== program start" + (" (SIMULATION)" if args.simulate else "") + " ===")

    sensor_classes = SIMULATED_SENSORS if args.simulate else REAL_SENSORS
    manager = SensorManager(sensor_classes, events)

    try:
        logger = DataLogger(config.LOG_DIRECTORIES, manager.columns(), config.LOG_FILE_PREFIX)
    except RuntimeError as e:
        events.log(f"FATAL: {e}")
        manager.close_all()
        return 1
    events.log("logging to: " + ", ".join(logger.open_files()))

    display = start_display(events)

    next_measurement = time.monotonic()
    try:
        while not stop_requested["value"]:
            values, errors = manager.read_all()
            logger.write(values, errors)

            if display is not None:
                try:
                    display.show(values, errors)
                except Exception as e:
                    events.log(f"display error: {e}")

            if args.verbose or logger.measurement_no % STATUS_EVERY_N_MEASUREMENTS == 1:
                print(f"#{logger.measurement_no} {format_status(values, errors)}", flush=True)

            if args.once:
                break
            if args.max_measurements is not None and logger.measurement_no >= args.max_measurements:
                break

            # Wait until the next measurement is due. If a reading took longer
            # than the interval, continue immediately instead of "catching up".
            next_measurement += args.interval
            remaining = next_measurement - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            else:
                next_measurement = time.monotonic()
    finally:
        events.log("shutting down")
        manager.close_all()
        logger.close()
        if display is not None:
            display.close()
        events.log("=== program end ===")
        events.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
