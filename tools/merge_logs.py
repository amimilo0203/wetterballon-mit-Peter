"""
merge_logs.py - Joins all flight_*.csv files of a flight into ONE csv file.

Every program start (and every power cut) creates a new file. For Excel or
LibreOffice it is easier to have everything in one file. Broken rows (cut
off by a power cut) are skipped and counted.

Usage (from the project folder):
    python tools/merge_logs.py                       reads data/, writes data/merged.csv
    python tools/merge_logs.py --data /media/usb/x   another data directory
    python tools/merge_logs.py --out flight.csv      another output file

Two extra columns are added at the front:
    file        - which file the row came from
    restart_no  - 1 for the first file, 2 for the second, ...
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.flight_data import load_all  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Merge all flight CSV files into one")
    parser.add_argument("--data", default="data", help="directory with the flight_*.csv files")
    parser.add_argument("--out", default=None, help="output file (default: <data>/merged.csv)")
    parser.add_argument("--prefix", default="flight", help="file name prefix (default: flight)")
    args = parser.parse_args()

    if not os.path.isdir(args.data):
        print(f"Directory not found: {args.data}")
        return 1

    columns, rows, files = load_all(args.data, args.prefix)
    if not files:
        print(f"No {args.prefix}_*.csv files found in {args.data}")
        return 1

    out_path = args.out or os.path.join(args.data, "merged.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as out_file:
        writer = csv.DictWriter(out_file, fieldnames=columns, restval="")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'file':<20} {'rows':>7} {'broken':>7}  first time -> last time")
    for info in files:
        print(f"{info['name']:<20} {info['rows']:>7} {info['broken_rows']:>7}  "
              f"{info['first_time']} -> {info['last_time']}")
    print(f"\n{len(rows)} rows from {len(files)} files written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
