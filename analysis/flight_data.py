"""
flight_data.py - Reads the flight_*.csv files back in, tolerating broken rows.

Used by analysis/analyze.py and tools/merge_logs.py. Only needs the Python
standard library, so it also runs on the Raspberry Pi without extra packages.

Why "tolerating broken rows"? If the power fails while a row is being
written, that last row is cut off in the middle. Such a row has fewer fields
than the header (or a mangled timestamp) and is simply skipped and counted.
"""

import csv
import os
import re


def find_flight_files(directory, prefix="flight"):
    """Returns the paths of all <prefix>_NNNN.csv files, sorted by number."""
    pattern = re.compile(r"^" + re.escape(prefix) + r"_(\d+)\.csv$")
    found = []
    for name in os.listdir(directory):
        match = pattern.match(name)
        if match:
            found.append((int(match.group(1)), os.path.join(directory, name)))
    return [path for _, path in sorted(found)]


def _looks_like_timestamp(text):
    # e.g. 2026-09-18T18:05:17
    return re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text) is not None


def load_rows(path):
    """
    Reads one CSV file. Returns (columns, rows, broken_count) where rows is a
    list of dictionaries {column: text}. Values are NOT converted to numbers
    here; that is up to the caller.
    """
    rows = []
    broken = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as file:
        reader = csv.reader(file)
        try:
            columns = next(reader)
        except StopIteration:
            return [], [], 0   # empty file (power failed right after creating it)
        for fields in reader:
            if not fields:
                continue
            if len(fields) != len(columns) or not _looks_like_timestamp(fields[0]):
                broken += 1
                continue
            rows.append(dict(zip(columns, fields)))
    return columns, rows, broken


def load_all(directory, prefix="flight"):
    """
    Loads every flight file in the directory.

    Returns (columns, rows, files):
      columns - union of all column names, in order of first appearance, plus
                "file" and "restart_no" at the front
      rows    - list of dictionaries, in file order
      files   - list of {"path", "name", "rows", "broken_rows", "first_time", "last_time"}
    """
    all_columns = ["file", "restart_no"]
    all_rows = []
    files = []
    for restart_no, path in enumerate(find_flight_files(directory, prefix), start=1):
        columns, rows, broken = load_rows(path)
        for column in columns:
            if column not in all_columns:
                all_columns.append(column)
        name = os.path.basename(path)
        for row in rows:
            row["file"] = name
            row["restart_no"] = restart_no
        all_rows.extend(rows)
        files.append({
            "path": path,
            "name": name,
            "rows": len(rows),
            "broken_rows": broken,
            "first_time": rows[0]["time"] if rows else "",
            "last_time": rows[-1]["time"] if rows else "",
        })
    return all_columns, all_rows, files
