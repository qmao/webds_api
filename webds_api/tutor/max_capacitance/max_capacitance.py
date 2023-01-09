import sys
import re
import time
import numpy as np


class MaxCapacitance():
    REPORT_ID = 18
    _handle = None
    _start = None
    _callback = None
    _terminate = False
    _terminated = False
    _max = -sys.maxsize - 1
    _cumMax = -sys.maxsize - 1

    def __init__(self, handle, callback=print):
        print("__init__")
        self._handle = handle
        self._callback = callback

    def init(self):
        print("init")
        self._start = None
        self._terminate = False
        self._terminated = False

        self._handle.disableReport(17)
        self._handle.disableReport(19)

    def set_report(self, enable, report):
        if enable:
            ret = self._handle.enableReport(report)
        else:
            ret = self._handle.disableReport(report)
        return True

    def get_report(self):
        try:
            report = self._handle.getReport(0.5)
            if report[0] == 'delta':
                return report[1]['image']
        except Exception as e:
            print("[get_report error]", str(e))
            pass
        return None

    def print_time(self, tag):
        if False:
            if self._start == None:
                self._start = time.time()
            now = time.time()
            print("[ TIME ]", tag, "--- %s seconds ---" % (now - self._start))
            self._start = now

    def update_info(self, data, state = "run"):
        self._callback({"state": state, "value": data})

    def run(self):
        try:
            self.init()
            self.set_report(True, self.REPORT_ID)
            self._terminated = self._terminate
            while self._terminate is False:
                report = self.get_report()
                if report is not None:
                    self._max = np.amax(report)
                    self._cumMax = max(self._max, self._cumMax)
                    self.update_info({"max": int(self._max), "cum_max": int(self._cumMax)}, "run")

            print("run While loop terminate")
            self._terminated = True
        except e as Exception:
            print(str(e))
        return

    def terminate(self):
        self._terminate = True
        while True:
            if self._terminated:
                break
            time.sleep(0.005)
        print("Terminated!")

    def reset(self):
        self._max = -sys.maxsize - 1
        self._cumMax = -sys.maxsize - 1