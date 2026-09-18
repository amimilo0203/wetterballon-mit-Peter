"""
data_logger.py - Saves measurements so that they survive a power cut.

The problem
-----------
When a program writes to a file, the data first only lands in a buffer in
RAM. The operating system writes it to the SD card "at some later point".
If the power fails in that moment, the last seconds to minutes of
measurements are lost.

The solution (what this logger does differently)
------------------------------------------------
1. After EVERY measurement row, flush() and os.fsync() are called. Only after
   that is the row guaranteed to be physically on the SD card.
2. Every program start creates a NEW file with a running number
   (flight_0001.csv, flight_0002.csv, ...). Existing files are never opened
   or overwritten. After a power cut and reboot, logging simply continues in
   the next file. The file numbers even tell you how often the Pi restarted.
3. Rows can be written to several directories at once (e.g. SD card AND a USB
   stick). If one of them fails, the others keep working.
4. Write errors never crash the program. The logger regularly retries a
   directory that has failed (e.g. a USB stick that was unplugged).

The file format is CSV (comma-separated values). It opens directly in Excel,
LibreOffice or Python (pandas). The first line holds the column names.

Worst case: the power fails while a row is being written. Then exactly that
one row is incomplete. All rows before it are safe. The analysis tools in
this project detect such broken rows and skip them.
"""

import csv
import datetime
import os
import re
import time


class DataLogger:
    """Writes measurements row by row, power-cut-safe, into CSV files."""

    # These columns are added automatically before / after the sensor columns:
    #   time            - clock time of the Raspberry Pi (only reliable if the
    #                     clock is correct, see README section "Uhrzeit")
    #   uptime_s        - seconds since program start (always reliable because
    #                     it does not depend on the clock setting)
    #   measurement_no  - running number of the measurement within this file
    #   errors          - which sensors could NOT be read in this measurement
    COLUMNS_FRONT = ["time", "uptime_s", "measurement_no"]
    COLUMNS_BACK = ["errors"]

    # How often (seconds) a failed directory is retried.
    RETRY_INTERVAL_S = 30

    def __init__(self, directories, sensor_columns, prefix="flight"):
        """
        directories    - list of folders to write into.
        sensor_columns - list of the column names the sensors deliver.
        prefix         - start of the file name, e.g. "flight" -> flight_0001.csv
        """
        self.columns = self.COLUMNS_FRONT + list(sensor_columns) + self.COLUMNS_BACK
        self.prefix = prefix
        self.measurement_no = 0
        self.start_time = time.monotonic()

        # Per directory we remember: the open file (or None if currently
        # failed), the CSV writer, the path and when we last tried to open it.
        self._targets = []
        for directory in directories:
            target = {"directory": directory, "file": None, "writer": None,
                      "path": None, "last_attempt": 0.0}
            self._targets.append(target)
            self._open_new_file(target)

        if not self.open_files():
            raise RuntimeError(
                "Could not write to ANY of the log directories: " + ", ".join(directories)
            )

    # ------------------------------------------------------------------ public

    def write(self, values, errors=()):
        """
        Writes ONE measurement row into every open file.

        values - dictionary {column_name: value}. Missing columns stay empty.
        errors - list of texts, e.g. ["bme280: Remote I/O error"]. Written as
                 one cell into the "errors" column.
        """
        self.measurement_no += 1

        row = dict(values)
        row["time"] = datetime.datetime.now().isoformat(timespec="seconds")
        row["uptime_s"] = round(time.monotonic() - self.start_time, 1)
        row["measurement_no"] = self.measurement_no
        row["errors"] = " | ".join(errors)

        for target in self._targets:
            if target["file"] is None:
                self._maybe_reopen(target)
            if target["file"] is None:
                continue
            try:
                target["writer"].writerow(row)
                self._force_to_disk(target["file"])
            except OSError as e:
                # For example: USB stick unplugged, SD card full.
                print(f"[DataLogger] Write error in {target['path']}: {e}", flush=True)
                self._close_file(target)

    def open_files(self):
        """Returns the paths of all files that are currently being written to."""
        return [t["path"] for t in self._targets if t["file"] is not None]

    def close(self):
        """Call this at program end. Closes all files cleanly."""
        for target in self._targets:
            self._close_file(target)

    # ------------------------------------------------------------------ internal

    def _open_new_file(self, target):
        """Creates a new file with the next free number in the directory."""
        directory = target["directory"]
        target["last_attempt"] = time.monotonic()
        try:
            os.makedirs(directory, exist_ok=True)
            number = self._next_free_number(directory)
            path = os.path.join(directory, f"{self.prefix}_{number:04d}.csv")

            # Mode "x" = create a new file, error if it already exists.
            # This guarantees that we can never overwrite anything.
            file = open(path, "x", newline="", encoding="utf-8")
            writer = csv.DictWriter(
                file,
                fieldnames=self.columns,
                restval="",              # missing values -> empty cell
                extrasaction="ignore",   # unknown columns -> ignored
            )
            writer.writeheader()
            self._force_to_disk(file)
            self._sync_directory(directory)

            target["file"] = file
            target["writer"] = writer
            target["path"] = path
            print(f"[DataLogger] Writing to {path}", flush=True)
        except OSError as e:
            print(f"[DataLogger] Directory {directory} not usable: {e}", flush=True)
            target["file"] = None

    def _maybe_reopen(self, target):
        """Retries a failed directory every few seconds."""
        elapsed = time.monotonic() - target["last_attempt"]
        if elapsed >= self.RETRY_INTERVAL_S:
            self._open_new_file(target)

    def _close_file(self, target):
        if target["file"] is not None:
            try:
                target["file"].close()
            except OSError:
                pass
        target["file"] = None
        target["writer"] = None

    def _next_free_number(self, directory):
        """Finds the highest existing number (flight_0007.csv -> 7) and returns +1."""
        pattern = re.compile(r"^" + re.escape(self.prefix) + r"_(\d+)\.csv$")
        highest = 0
        for name in os.listdir(directory):
            match = pattern.match(name)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    @staticmethod
    def _force_to_disk(file):
        """
        The most important step: force the data out of the buffers onto the
        SD card. flush() empties Python's buffer into the operating system,
        os.fsync() forces the operating system to write to the storage device.
        """
        file.flush()
        os.fsync(file.fileno())

    @staticmethod
    def _sync_directory(directory):
        """
        The directory entry must be synced too. Otherwise, after a power cut,
        the new file may exist on disk but be "invisible" in the folder.
        (Only needed and possible on Linux; skipped on Windows.)
        """
        if os.name != "posix":
            return
        try:
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass


class EventLog:
    """
    Writes events (start, sensor found, sensor failed, ...) with a timestamp
    into the text file events.log and at the same time to the screen.

    This helps after the flight to reconstruct what happened when.
    Every line is secured with fsync here as well.
    """

    def __init__(self, directory, file_name="events.log"):
        self._file = None
        self.path = None
        try:
            os.makedirs(directory, exist_ok=True)
            self.path = os.path.join(directory, file_name)
            self._file = open(self.path, "a", encoding="utf-8")
        except OSError as e:
            print(f"[EventLog] Cannot use {directory}: {e}", flush=True)

    def log(self, text):
        """Writes one line with timestamp to the file and to the screen."""
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        line = f"{timestamp}  {text}"
        print(line, flush=True)
        if self._file is None:
            return
        try:
            self._file.write(line + "\n")
            self._file.flush()
            os.fsync(self._file.fileno())
        except OSError as e:
            print(f"[EventLog] Write error: {e}", flush=True)

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
