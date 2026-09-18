"""
test_sensor.py - Try out ONE sensor on its own.

This replaces the old single-sensor scripts (CO2.py, MQ9.py, ...). It starts
the sensor, prints a reading every second and shows errors instead of
crashing, so you can wiggle cables and watch what happens.

Usage (from the project folder):
    python tools/test_sensor.py --list            show the available sensor names
    python tools/test_sensor.py bme280            read the BME280 every second
    python tools/test_sensor.py co2 --interval 5  read the CO2 sensor every 5 s
    python tools/test_sensor.py uv --simulate     fake values, no hardware needed
Stop with Ctrl+C.
"""

import argparse
import os
import sys
import time

# Make the project folder importable, no matter from where this script is started.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensors import REAL_SENSORS, SIMULATED_SENSORS  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Test a single sensor")
    parser.add_argument("name", nargs="?", help="sensor name, see --list")
    parser.add_argument("--list", action="store_true", help="list sensor names and exit")
    parser.add_argument("--simulate", action="store_true", help="use the fake sensor")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    args = parser.parse_args()

    classes = SIMULATED_SENSORS if args.simulate else REAL_SENSORS

    if args.list or not args.name:
        print("Available sensors:")
        for name, cls in classes.items():
            print(f"  {name:10s} -> columns: {', '.join(cls.COLUMNS)}")
        return 0

    if args.name not in classes:
        print(f"Unknown sensor '{args.name}'. Use --list to see the names.")
        return 1

    print(f"Starting sensor '{args.name}' ...")
    try:
        sensor = classes[args.name]()
    except Exception as e:
        print(f"Could not start the sensor: {e}")
        print("Check wiring, I2C/SPI/UART settings and the addresses in config.py.")
        return 1
    print("Sensor started. Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                values = sensor.read()
                print("  ".join(f"{column}={value}" for column, value in values.items()))
            except Exception as e:
                print(f"ERROR: {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sensor.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
