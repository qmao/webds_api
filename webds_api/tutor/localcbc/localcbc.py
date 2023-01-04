import sys
import re
import time


def update_static_config(handle, config, configToSet):
    try:
        for key in configToSet:
            config_value = configToSet[key]
            print(key, '->', config_value)
            if isinstance(config_value, list):
                for idx, x in enumerate(config_value):
                    config[key][idx] = int(x)
            else:
                config[key] = int(config_value)

        handle.setStaticConfig(config)

    except Exception as e:
        raise Exception(str(e))
    return config

def update_dynamic_config(handle, config, configToSet):
    try:
        for key in configToSet:
            config_value = configToSet[key]
            print(key, '->', config_value)
            if isinstance(config_value, list):
                for idx, x in enumerate(config_value):
                    config[key][idx] = int(x)
            else:
                config[key] = int(config_value)

        handle.setDynamicConfig(config)

    except Exception as e:
        raise Exception(str(e))
    return config

class SortedData():
    _list = []

    def __init__(self):
        self._list = []

    def get_median(self):
        # sort the list
        ls = self._list
        ls_sorted = ls.sort()
        # find the median
        if len(ls) % 2 != 0:
            # total number of values are odd
            # subtract 1 since indexing starts at 0
            m = int((len(ls)+1)/2 - 1)
            return ls[m]
        else:
            m1 = int(len(ls)/2 - 1)
            m2 = int(len(ls)/2)
            return int((ls[m1]+ls[m2])/2)

    def Add(self, value):
        self._list.append(value)


class IntStatisticsSet():
    _Count = 0
    _Sum = 0
    _Mean = 0
    _Median = 0
    _Min = sys.maxsize
    _Max = -sys.maxsize - 1
    _MinOfMax = sys.maxsize
    _MaxOfMin = -sys.maxsize - 1
    _sortedData = SortedData()

    _LocalMin = sys.maxsize
    _LocalMax = -sys.maxsize - 1
    _subchannels = []

    def reset(self):
        self._Count = 0
        self._Sum = 0
        self._Mean = 0
        self._Median = 0
        self._Min = sys.maxsize
        self._Max = -sys.maxsize - 1
        self._MinOfMax = sys.maxsize
        self._MaxOfMin = -sys.maxsize - 1
        self._sortedData = SortedData()
        self._subchannels = []

    def __init__(self):
        self.reset()

    def process(self, data, perChannel=False):
        self._LocalMin = sys.maxsize
        self._LocalMax = -sys.maxsize - 1

        for i in range(len(data)):
            item = data[i]
            self._sortedData.Add(item)

            if perChannel:
                if i == len(self._subchannels):
                    obj = IntStatisticsSet()
                    self._subchannels.append(obj)

                sc = self._subchannels[i];
                sc.process([item])

            self._Count = self._Count + 1
            self._Sum = self._Sum + item;
            self._Min = min(self._Min, item)
            self._Max = max(self._Max, item)
            self._LocalMin = min(self._LocalMin, item)
            self._LocalMax = max(self._LocalMax, item)

        self._MinOfMax = min(self._MinOfMax, self._LocalMax)
        self._MaxOfMin = max(self._MaxOfMin, self._LocalMin)
        self._Mean = (self._Sum) / self._Count
        self._Median = self._sortedData.get_median()

    def get_channels(self):
        return self._subchannels

    def get_median(self):
        return self._Median

    def get_max(self):
        return self._Max

    def get_min(self):
        return self._Min

    def print_result(self):
        if False:
            print("Param: ", self._Count, self._Sum, self._Min, self._Max, self._LocalMin, self._LocalMax, self._MinOfMax, self._MaxOfMin, self._Mean, self._Median)

class LocalCBC():
    _handle = None
    _callback = None
    _start = None
    _debug = False
    _terminate = False
    _terminated = False
    _static_config = {}
    _dynamic_config = {}

    def __init__(self, handle, callback=print):
        self._handle = handle
        self._callback = callback
        self._static_config = self._handle.getStaticConfig()
        self._dynamic_config = self._handle.getDynamicConfig()
        self._touch_info = self._handle.getTouchInfo()
        self._app_info = self._handle.getAppInfo()

        self._terminate = False
        self._terminated = False

    def after_run(self):
        self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"requestedNoiseMode": self._dynamic_config["requestedNoiseMode"]})
        self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"noLowPower": self._dynamic_config["noLowPower"]})
        if "adnsEnabled" in self._static_config:
            self._static_config = update_static_config(self._handle, self._static_config, {"adnsEnabled": self._static_config["adnsEnabled"]})

    def before_run(self):
        self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"requestedNoiseMode": 5})
        self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"noLowPower": 1})
        if "adnsEnabled" in self._static_config:
            self._static_config = update_static_config(self._handle, self._static_config, {"adnsEnabled": 0})


    def getSignalClarityType(self):
        if "signalClarityOrder" in self._touch_info:
            value = self._touch_info.get("signalClarityOrder", 0)
            return value >= 0
        return False

    def get_signal_clarity_enable(self):
        if "signalClarityOrder" in self._touch_info:
            value = self._static_config["signalClarityEnable"]
            return value
        return False

    def init(self):
        print("init")
        self._handle.disableReport(17)
        self._handle.disableReport(18)
        self._handle.disableReport(19)

    def update_image_cbcs(self, data):
        self._static_config = update_static_config(self._handle, self._static_config, {"imageCBCs": data})

    def set_report(self, enable, report):
        try:
            if enable:
                ret = self._handle.enableReport(report)
            else:
                ret = self._handle.disableReport(report)
        except:
            print("set report error, ignore")
            pass

        return True

    def get_report(self, reportId):
        for i in range(5):
            try:
                report = self._handle.getReport()
                if report == ('timeout', None):
                    continue
                if report[0] == reportId:
                    ## print("data: ", ''.join('{:02x}'.format(x) for x in report[1]))
                    return report[1]
            except:
                pass
        raise Exception('cannot get valid report')

    def get_row(self, data, row, column, numButtons, cdmOrder):
        arr = []
        for c in range(column):
            arrRow = []
            for r in range(row):
                arrRow.append((data[c * row * 2 + r * 2] + (data[c * row * 2 + r * 2 + 1] << 8)))
            arr.append(arrRow)
        return arr

    def print_time(self, tag):
        if self._debug:
            if self._start == None:
                self._start = time.time()
            now = time.time()
            print("[ TIME ]", tag, "--- %s seconds ---" % (now - self._start))
            self._start = now

    def convert_cbcs_value(self, data, count):
        base = (count + 1) / 2 

        arr = []
        for i in data:
            value = 0
            if i < base:
               value = i * 0.5
            else:
               value = 0 - ((i - base) * 0.5)
            print(i, "=>",value)
            arr.append(value)
        return arr

    def convert_cbcs_valueToBase(data):
        arr = []
        for i in data:
            value = 0
            if i is 0:
                value = 32
            if i > 0:
               value = i * 2
            else:
               value = abs(i * 2) + 32
            print(i, "=>",value)
            arr.append(value)
        return arr

    def update_progress(self, progress):
        self._callback({"state": "run", "progress": progress})

    def run(self, samplesLimit):
        self._terminated = self._terminate
        self.init()

        self.before_run()
        ### global
        _CBC_flagPolarity = 0x20

        adcRange = 4096
        reportId = 31  ###195
        cbcAvailableValues = 63
        txCount = self._static_config["txCount"]
        rxCount = self._static_config["rxCount"]
        numButtons = self._app_info["numButtons"]
        signalClarityEnabled = self.get_signal_clarity_enable()
        cdmOrder = self.getSignalClarityType()

        if "imageBurstsPerCluster" in self._static_config:
            burstsPerCluster = self._static_config["imageBurstsPerCluster"]
        elif "imageBurstsPerClusterQF" in self._static_config:
            burstsPerCluster = self._static_config["imageBurstsPerClusterQF"]
        elif "imageBurstsPerClusterMF" in self._static_config:
            burstsPerCluster = self._static_config["imageBurstsPerClusterMF"]

        realReportId = 0
        response = []
        numofsteps = int((cbcAvailableValues + 1) / 2);
        stepPercentage = 100 / (numofsteps * samplesLimit)
        currentPercent = 0

        # item1 is best score, item 2 is index of best score
        bestScores = [[sys.maxsize, -1]] * rxCount
        polarity = [False] * rxCount

        self.print_time("Start")
        # 1. Set Image CBC for each enabled Rx to 0. 
        # For Gluon, setting CBC_CHn to 0 means that the local CBC for that channel is off.
        # There is no separate CBC_CARRIER_SEL value for each Rx.
        for step in range(numofsteps):
            array_ = [0] * rxCount
            for index in range(rxCount):
                value = 0x00
                if polarity[index]:
                    value = _CBC_flagPolarity
                array_[index] = step | value
            self.update_image_cbcs(array_)
            self.print_time("update_image_cbcs")

            status = self.set_report(True, reportId)
            self.print_time("set_report")

            if status == False:
                print("transaction failed")
                raise Exception('set_report transaction failed')

            if self._terminate:
                print("user terminate")
                break

            currentPercent = step * samplesLimit * stepPercentage;
            self.update_progress(currentPercent)

            samples = []
            # start data collecting
            for samplesCollected in range(samplesLimit):
                ###print("LOOP:", step, samplesCollected)
                if self._terminate:
                    print("user terminate")
                    break

                data = self.get_report(reportId)
                self.print_time("get_report")

                samples.append(data)
                progress = currentPercent + (samplesCollected * stepPercentage)
                self.update_progress(progress)

            # stop data collecting
            status = self.set_report(False, reportId)
            self.print_time("set_report disable")

            # Calculate stats
            statisticsSet = IntStatisticsSet()

            for sample in samples:
                if len(sample) == 0:
                    raise Exception('cannot get valid report')
                rows = self.get_row(sample, rxCount, txCount, numButtons, cdmOrder)
                for row in rows:
                    statisticsSet.process(row, True)

            # Calculate the best scores
            statisticsRows = statisticsSet.get_channels()

            for idx, i in enumerate(statisticsRows):
                if step is 0:
                    if i.get_max() < 3000:
                        adcRange = 2048

                i.print_result()

                lmin = i.get_min()
                lmax = i.get_max()
                ## intvar = i.get_median()
                ## score = (intvar - 4096) / burstsPerCluster    # Juneau Specific - 13bit ADC (SWDS6-3161)

                scoreNext = 0
                scorePrev = 0
                if idx is not 0:
                    scorePrev = abs((statisticsRows[idx - 1].get_max() - adcRange) - (adcRange - statisticsRows[idx - 1].get_min()))
                if idx is not (rxCount -1):
                    scoreNext = abs((statisticsRows[idx + 1].get_max() - adcRange) - (adcRange - statisticsRows[idx + 1].get_min()))
                score = abs((lmax - adcRange) - (adcRange - lmin)) + scorePrev + scoreNext

                if abs(score) < abs(bestScores[idx][0]):
                    bestScores[idx] = [score, step]
            if self._debug:
                print("BEST SCORE: ", bestScores)

            # 5.For CBC off (== 0) For each receiver, if Score is positive, 
            # set CBC TX Pl for that receiver = 0 (charge subtraction). 
            # If Score is negative, set CBC TX Pl for that receiver = 1 (charge addition).
            if step == 0:
                for i in range(rxCount):
                    if bestScores[i][0] < 0:
                        polarity[i] = False
                    else:
                        polarity[i] = True
                if self._debug:
                    print("polarity: ", polarity)

        if self._terminate:
            self._terminated = True
            self.after_run()
            return {"data": "cancel"}

        # set best cbcs to memory
        bestValues = [0] * len(bestScores)

        for idx, i in enumerate(bestScores):
            bestValues[idx] = i[1]
            if bestValues[idx] != 0:
                if polarity[idx]:
                    bestValues[idx] = bestValues[idx] | _CBC_flagPolarity
                else:
                    bestValues[idx] = bestValues[idx] & ~_CBC_flagPolarity

        print("[Best]: ", bestValues)

        self.after_run()
        self.update_image_cbcs(bestValues)
        self.update_progress(100)
        return self.convert_cbcs_value(bestValues, cbcAvailableValues)

    def terminate(self):
        self._terminate = True
        while True:
            if self._terminated:
                break
            time.sleep(0.005)
        print("Terminated!")