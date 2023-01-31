import sys
import numpy as np

class SampleModule():
    _tc = None
    _reports = None
    _max = -sys.maxsize - 1

    def __init__(self, tc):
        self._tc = tc

    def collect(self):
        self._tc.disableReport(17)
        self._tc.enableReport(18)

        report = self._tc.getReport()
        if report[0] == 'delta':
            report = report[1]['image']
            self._reports = report

        self._tc.disableReport(18)
        self._tc.enableReport(17)

    def tune(self):
        if self._reports is not None:
            self._max = int(np.amax(self._reports))
        else:
            print("report none")