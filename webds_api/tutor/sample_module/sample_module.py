from touchcomm import TouchComm
import numpy as np
import sys

import sys
import numpy as np
import json

TARGETS = {"saturationLevel"}

class SampleModule():

    def __init__(self, tc):
        self._tc = tc
        self._reports = []
        self._count = 0
        self._sc = tc.getStaticConfig()

    def collect(self, count):
        self._count = count
        self._tc.reset()
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
            cum_max = int(np.amax(self._reports))
            self._sc["saturationLevel"] = cum_max
            self._tc.setStaticConfig(self._sc)
        else:
            print("unmatched sample count", len(self._reports), self._count)

    def get_configuration(self):
        config = {}
        for target in TARGETS:
            config[target] = self._sc[target]
        return config