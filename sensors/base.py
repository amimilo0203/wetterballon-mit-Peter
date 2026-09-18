"""
base.py - The common foundation of all sensors.

Every sensor class inherits from Sensor and defines:
  - NAME:     short name for messages ("bme280", "co2", ...)
  - COLUMNS:  which columns the sensor delivers into the CSV file
  - read():   reads the sensor once and returns {column: value}

Rules every sensor class follows:
  * The constructor (__init__) opens the connection to the sensor. If that
    fails it raises an exception. The main program catches it and retries
    later.
  * read() may raise an exception if reading fails. The main program catches
    it, writes it into the "errors" column and continues with the other
    sensors.
  * read() must never block forever. Waiting loops need a time limit
    (see wait_until below).
"""

import time


class Sensor:
    NAME = "unnamed"
    COLUMNS = []

    def read(self):
        """Reads the sensor once. Must be overridden by every subclass."""
        raise NotImplementedError(f"{self.NAME}: read() is not implemented")

    def close(self):
        """Called at program end. Close connections here if needed."""
        pass


def wait_until(condition, timeout_s, poll_interval_s=0.005, description="condition"):
    """
    Helper: calls condition() until it returns True.
    If that takes longer than timeout_s seconds, a TimeoutError is raised.

    This replaces "while True: ..." loops, which would freeze the whole
    program forever if a cable comes loose.
    """
    deadline = time.monotonic() + timeout_s
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Timeout ({timeout_s} s) while waiting for: {description}")
        time.sleep(poll_interval_s)
