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
    _report_id = 18
    def __init__(self):
        self._queue = SSEQueue()
        self._tc = TouchcommManager()
        self._config_handler = ConfigHandler(self._tc)


    def init(self):
        print("init")
        self._tc.disableReport(17)
        self._tc.disableReport(19)

    def setReport(self, enable, report):
        if enable:
            ret = self._tc.enableReport(report)
        else:
            ret = self._tc.disableReport(report)
        return True

    def getReport(self):
        for i in range(10):
            try:
                report = self._tc.getReport()
                if report == ('timeout', None):
                    continue
                if report[0] == 'delta':
                    return report[1]['image']
            except:
                pass
        raise Exception('cannot get valid report')

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
        _max = -sys.maxsize - 1
        _cumMax = -sys.maxsize - 1

        try:
            self.init()
            self.setReport(True, self._report_id)
            while self._terminate is False:
                report = self.getReport()
                _max = np.amax(report)
                _cumMax = max(_max, _cumMax)
                self.updateInfo({"max": int(_max), "cum_max": int(_cumMax)}, "run")
        except e as Exception:
            print(str(e))
        return