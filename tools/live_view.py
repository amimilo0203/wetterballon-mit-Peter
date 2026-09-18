"""
live_view.py - Watch the newest measurements in the terminal while the logger runs.

Useful before launch: are all sensors delivering plausible values? It only
READS the newest flight_*.csv file, so it can run at the same time as main.py
(also over SSH). It never touches the running logger.

Usage (from the project folder):
    python tools/live_view.py                 refresh every 2 seconds
    python tools/live_view.py --interval 1    refresh every second
    python tools/live_view.py --data /media/usb/weather-balloon
Stop with Ctrl+C.
"""

import argparse
import csv
import datetime
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.flight_data import find_flight_files  # noqa: E402

TAIL_BYTES = 16_000  # more than enough for the header + last few rows


def read_last_row(path):
    """Returns (columns, last complete row as dict) or (columns, None)."""
    with open(path, "rb") as file:
        header = file.readline().decode("utf-8", errors="replace").strip()
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(max(len(header) + 1, size - TAIL_BYTES))
        tail = file.read().decode("utf-8", errors="replace")

    columns = next(csv.reader(io.StringIO(header)))
    # Only lines that end with a newline are complete
    complete_lines = [line for line in tail.split("\n")[:-1] if line.strip()]
    for line in reversed(complete_lines):
        fields = next(csv.reader(io.StringIO(line)))
        if len(fields) == len(columns) and fields[0] != columns[0]:
            return columns, dict(zip(columns, fields))
    return columns, None


def seconds_since(timestamp_text):
    try:
        then = datetime.datetime.fromisoformat(timestamp_text)
        return (datetime.datetime.now() - then).total_seconds()
    except ValueError:
        return None


def render(path, columns, row):
    lines = ["=== weather balloon live view ===", f"file: {path}"]
    if row is None:
        lines.append("(no complete row yet)")
        return "\n".join(lines)

    age = seconds_since(row.get("time", ""))
    age_text = f"{age:.0f} s ago" if age is not None else "unknown"
    warning = "   <-- STALE! is main.py running?" if age is not None and age > 30 else ""
    lines.append(f"last row: #{row.get('measurement_no')} at {row.get('time')} ({age_text}){warning}")
    lines.append("")

    skip = {"time", "uptime_s", "measurement_no", "errors"}
    for column in columns:
        if column in skip:
            continue
        value = row.get(column, "")
        lines.append(f"  {column:<24} {value if value != '' else '--'}")

    lines.append("")
    errors = row.get("errors", "")
    lines.append(f"errors: {errors if errors else 'none'}")
    lines.append("\n(Ctrl+C to quit)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Live view of the newest measurements")
    parser.add_argument("--data", default="data", help="directory with the flight_*.csv files")
    parser.add_argument("--prefix", default="flight", help="file name prefix")
    parser.add_argument("--interval", type=float, default=2.0, help="refresh seconds")
    args = parser.parse_args()

    try:
        while True:
            files = find_flight_files(args.data, args.prefix) if os.path.isdir(args.data) else []
            if not files:
                text = f"No {args.prefix}_*.csv files in {args.data} yet. Waiting ..."
            else:
                columns, row = read_last_row(files[-1])
                text = render(files[-1], columns, row)
            print("\033[2J\033[H" + text, flush=True)   # clear screen, move cursor home
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
