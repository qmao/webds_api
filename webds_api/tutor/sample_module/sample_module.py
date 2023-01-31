import sys
import numpy as np
import json

class SampleModule():

    def __init__(self, tc):
        self._tc = tc
        self._reports = []
        self._max = -sys.maxsize - 1
        self._count = 0

    def collect(self, count):
        self._count = count
        self._tc.disableReport(17)
        self._tc.enableReport(18)

        for x in range(count):
            report = self._tc.getReport()
            if report[0] == 'delta':
                report = report[1]['image']
                self._reports.append(report)
                print(json.dumps({"progress": x}))

        self._tc.disableReport(18)
        self._tc.enableReport(17)

    def tune(self):
        if len(self._reports) == self._count:
            self._max = int(np.amax(self._reports))
            print(self._max)
        else:
            print("unmatched sample count", len(self._reports), self._count)