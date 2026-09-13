# -*- coding: utf-8 -*-
"""
Event marker layer.

The idea: the experiment ALWAYS writes an event log with high-precision
timestamps. On top of that, depending on the equipment, it can send the
marker in real time over LSL, a serial port or a parallel port.

Why the CSV log is enough for this study: electrodermal responses (SCR) have
latencies of 1-4 s and are analysed in windows of seconds. Millisecond
precision like in an ERP is not needed. With Empatica E4 or Shimmer3 (which
record on their own clock) the standard procedure is exactly this: align
offline by timestamp.
"""

import csv
import time
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from psychopy import core, logging

import config
from common import protocol


class EventLog:
    """Writes every event to CSV and, when configured, sends it to the equipment."""

    def __init__(self, csv_path, clock, backend="csv"):
        self.clock = clock
        self.backend = backend
        self._send = None

        folder = os.path.dirname(csv_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self._file = open(csv_path, "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._file)
        self._csv.writerow([
            "t_experiment_s",    # seconds since the experiment started
            "t_unix",            # absolute timestamp, to align with the equipment
            "code",
            "label",
            "detail",
        ])

        self._open_backend()

    # -----------------------------------------------------------------
    def _open_backend(self):
        if self.backend == "lsl":
            try:
                from pylsl import StreamInfo, StreamOutlet
                info = StreamInfo("PsychoPy_Study1", "Markers", 1, 0,
                                  "int32", "study1_markers")
                outlet = StreamOutlet(info)
                self._send = lambda code: outlet.push_sample([int(code)])
                logging.info("LSL markers active.")
            except Exception as e:
                logging.warning("Could not open LSL (%s). Continuing with CSV only." % e)

        elif self.backend == "serial":
            try:
                import serial
                port = serial.Serial(config.SERIAL_PORT, config.SERIAL_BAUD,
                                     timeout=0)
                self._send = lambda code: port.write(bytes([int(code) & 0xFF]))
                logging.info("Serial port markers active.")
            except Exception as e:
                logging.warning("Could not open the serial port (%s). Continuing with CSV only." % e)

        elif self.backend == "parallel":
            try:
                from psychopy import parallel
                parallel.setPortAddress(config.PARALLEL_ADDRESS)

                def _pulse(code):
                    parallel.setData(int(code) & 0xFF)
                    core.wait(0.005)
                    parallel.setData(0)

                self._send = _pulse
                logging.info("Parallel port markers active.")
            except Exception as e:
                logging.warning("Could not open the parallel port (%s). Continuing with CSV only." % e)

    # -----------------------------------------------------------------
    def mark(self, label, detail=""):
        """Records an event. `label` must be in protocol/markers.json."""
        code = protocol.markers().get(label, 0)
        t_exp = self.clock.getTime()
        t_unix = time.time()

        if self._send is not None:
            try:
                self._send(code)
            except Exception as e:
                logging.warning("Failed to send marker %s: %s" % (label, e))

        self._csv.writerow(["%.4f" % t_exp, "%.6f" % t_unix, code, label, detail])
        self._file.flush()
        return t_exp

    def close(self):
        try:
            self._file.close()
        except Exception:
            pass
