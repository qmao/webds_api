import sys
import re
import time
import numpy as np
from ...touchcomm.touchcomm_manager import TouchcommManager
from ...configuration.config_handler import ConfigHandler
from ..tutor_utils import SSEQueue


class MaxCapacitanceManager():
    _tc = None
    _start = None
    _config_handler = None
    _queue = None
    _terminate = False
    _terminated = False
    _report_id = 18
    _max = -sys.maxsize - 1
    _cumMax = -sys.maxsize - 1

    def __init__(self):
        print("__init__")

    def init(self):
        print("init")
        self._tc = None
        self._start = None
        self._config_handler = None
        self._queue = None
        self._terminate = False
        self._terminated = False

        self._queue = SSEQueue()
        self._tc = TouchcommManager()
        self._config_handler = ConfigHandler(self._tc)

        self._tc.disableReport(17)
        self._tc.disableReport(19)

    def setReport(self, enable, report):
        if enable:
            ret = self._tc.enableReport(report)
        else:
            ret = self._tc.disableReport(report)
        return True

    def getReport(self):
        try:
            report = self._tc.getReport(0.5)
            if report[0] == 'delta':
                return report[1]['image']
        except Exception as e:
            print("[getReport error]", str(e))
            pass
        return None

    def printTime(self, tag):
        if False:
            if self._start == None:
                self._start = time.time()
            now = time.time()
            print("[ TIME ]", tag, "--- %s seconds ---" % (now - self._start))
            self._start = now


    def updateInfo(self, data, state = "run"):
        self._queue.setInfo("MaxCapacitance", {"state": state, "value": data})

    def run(self):
        try:
            self.init()
            self.setReport(True, self._report_id)
            self._terminated = self._terminate
            while self._terminate is False:
                report = self.getReport()
                if report is not None:
                    self._max = np.amax(report)
                    self._cumMax = max(self._max, self._cumMax)
                    self.updateInfo({"max": int(self._max), "cum_max": int(self._cumMax)}, "run")

            print("run While loop terminate")
            self._terminated = True
        except e as Exception:
            print(str(e))
        return

    def terminate(self):
        self.updateInfo({}, "terminate")
        self._terminate = True
        while True:
            if self._terminated:
                break
            time.sleep(0.005)
        print("Terminated!")

    def reset(self):
        self._max = -sys.maxsize - 1
        self._cumMax = -sys.maxsize - 1