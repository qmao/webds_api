import sys
import re
import time
import numpy as np

REPORT_ID = 18

class MaxCapacitance():
    REPORT_ID = 18
    _handle = None
    _start = None
    _max = -sys.maxsize - 1
    _cumMax = -sys.maxsize - 1

    def __init__(self, handle):
        print("__init__")
        self._handle = handle

    def init(self):
        print("init")
        self._start = None

        self._handle.disableReport(17)
        self._handle.disableReport(19)
        
        self.set_report(True, REPORT_ID)

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

    def run(self):
        try:
            report = self.get_report()
            if report is not None:
                self._max = np.amax(report)
                self._cumMax = max(self._max, self._cumMax)

        except e as Exception:
            print(str(e))
        return self._max, self._cumMax

    def reset(self):
        self._max = -sys.maxsize - 1
        self._cumMax = -sys.maxsize - 1