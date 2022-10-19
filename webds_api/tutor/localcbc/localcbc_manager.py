import sys
import re
import time
from ...touchcomm.touchcomm_manager import TouchcommManager
from ...configuration.config_handler import ConfigHandler
from ..tutor_utils import SSEQueue

class SortedData():
    _list = []

    def __init__(self):
        self._list = []

    def GetMedian(self):
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

    def Process(self, data, perChannel=False):
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
                sc.Process([item])

            self._Count = self._Count + 1
            self._Sum = self._Sum + item;
            self._Min = min(self._Min, item)
            self._Max = max(self._Max, item)
            self._LocalMin = min(self._LocalMin, item)
            self._LocalMax = max(self._LocalMax, item)

        self._MinOfMax = min(self._MinOfMax, self._LocalMax)
        self._MaxOfMin = max(self._MaxOfMin, self._LocalMin)
        self._Mean = (self._Sum) / self._Count
        self._Median = self._sortedData.GetMedian()

    def GetChannels(self):
        return self._subchannels

    def GetMedian(self):
        return self._Median

    def printResult(self):
        if False:
            print("Param: ", self._Count, self._Sum, self._Min, self._Max, self._LocalMin, self._LocalMax, self._MinOfMax, self._MaxOfMin, self._Mean, self._Median)

class LocalCBCManager():
    _tc = None
    _start = None
    _config_handler = None
    _queue = None

    def __init__(self):
        self._queue = SSEQueue()
        self._tc = TouchcommManager()
        self._tc.getInstance().reset() #### fixme
        self._config_handler = ConfigHandler(self._tc)
        self._config_handler.update_dynamic_config({"requestedNoiseMode": 5})
        self._config_handler.update_dynamic_config({"noLowPower": 1})
        self._config_handler.update_static_config({"adnsEnabled": 0})

    def getSignalClarityType(self, data):
        if "signalClarityOrder" in data:
            value = data["signalClarityOrder"]
            return value >= 0
        return False

    def getSignalClarityEnable(self, data):
        if "signalClarityEnable" in data:
            value = data["signalClarityEnable"]
            return value
        return False

    def init(self):
        print("init")
        self._tc.disableReport(17)
        self._tc.disableReport(18)
        self._tc.disableReport(19)

    def updateImageCBCs(self, data):
        config = self._config_handler.update_static_config({"imageCBCs": data})

    def setReport(self, enable, report):
        try:
            if enable:
                ret = self._tc.enableReport(report)
            else:
                ret = self._tc.disableReport(report)
        except:
            print("set report error, ignore")
            pass

        return True

    def getReport(self, reportId):
        for i in range(5):
            try:
                report = self._tc.getReport()
                if report == ('timeout', None):
                    continue
                if report[0] == reportId:
                    ## print("data: ", ''.join('{:02x}'.format(x) for x in report[1]))
                    return report[1]
                else:
                    print("unmatched report: ", report)
            except:
                pass
        raise Exception('cannot get valid report')

    def getRow(self, data, row, column, numButtons, cdmOrder):
        arr = []
        for c in range(column):
            arrRow = []
            for r in range(row):
                arrRow.append((data[c * row * 2 + r * 2] + (data[c * row * 2 + r * 2 + 1] << 8)))
            arr.append(arrRow)
        return arr

    def printTime(self, tag):
        if False:
            if self._start == None:
                self._start = time.time()
            now = time.time()
            print("[ TIME ]", tag, "--- %s seconds ---" % (now - self._start))
            self._start = now

    def convertCBCSValue(self, data, count):
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

    def updateInfo(self, progress, state = "run"):
        self._queue.setInfo("LocalCBC", {"state": state, "progress": progress})

    def run(self, samplesLimit):
        self.init()
        ### global
        _CBC_flagPolarity = 0x20
        terminate = False

        reportId = 31  ###195
        cbcAvailableValues = 63

        static_config = self._config_handler.getStaticConfig()

        txCount = static_config["txCount"]
        rxCount = static_config["rxCount"]
        numButtons = static_config["numButtons"]
        signalClarityEnabled = self.getSignalClarityEnable(static_config)

        touch = self._tc.getInstance().getTouchInfo()
        print(touch)
        cdmOrder = self.getSignalClarityType(touch)
        burstsPerCluster = 1

        realReportId = 0
        response = []
        numofsteps = int((cbcAvailableValues + 1) / 2);
        stepPercentage = 100 / (numofsteps * samplesLimit);
        currentPercent = 0;

        print("Progress param:", signalClarityEnabled, cdmOrder, burstsPerCluster)

        # item1 is best score, item 2 is index of best score
        bestScores = [[sys.maxsize, -1]] * rxCount
        polarity = [False] * rxCount

        self.printTime("Start")
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
            self.updateImageCBCs(array_)
            self.printTime("updateImageCBCs")

            status = self.setReport(True, reportId)
            self.printTime("setReport")

            if status == False:
                print("transaction failed")
                raise Exception('setReport transaction failed')

            if terminate:
                print("user terminate")
                break

            currentPercent = step * samplesLimit * stepPercentage;
            self.updateInfo(currentPercent)

            samples = []
            # start data collecting
            for samplesCollected in range(samplesLimit):
                ###print("LOOP:", step, samplesCollected)
                if terminate:
                    print("user terminate")
                    break

                data = self.getReport(reportId)
                self.printTime("getReport")

                samples.append(data)
                progress = currentPercent + (samplesCollected * stepPercentage)
                self.updateInfo(progress)

            # stop data collecting
            status = self.setReport(False, reportId)
            self.printTime("setReport disable")

            # Calculate stats
            statisticsSet = IntStatisticsSet()

            for sample in samples:
                if len(sample) == 0:
                    raise Exception('cannot get valid report')
                rows = self.getRow(sample, rxCount, txCount, numButtons, cdmOrder)
                for row in rows:
                    statisticsSet.Process(row, True)

            # Calculate the best scores
            statisticsRows = statisticsSet.GetChannels()

            for idx, i in enumerate(statisticsRows):
                i.printResult()
                intvar = i.GetMedian()

                score = (intvar - 4096) / burstsPerCluster    # Juneau Specific - 13bit ADC (SWDS6-3161)
                if abs(score) < abs(bestScores[idx][0]):
                    bestScores[idx] = [score, step]
            if False:
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

        # set best cbcs to memory
        bestValues = [0] * len(bestScores)

        for idx, i in enumerate(bestScores):
            bestValues[idx] = i[1]
            if bestValues[idx] != 0:
                if polarity[idx]:
                    bestValues[idx] = bestValues[idx] | _CBC_flagPolarity
                else:
                    bestValues[idx] = bestValues[idx] & ~_CBC_flagPolarity
        if False:
            print("[Best]: ", bestValues)

        self.updateInfo(100, "run")
        self.updateInfo(100, "stop")

        return self.convertCBCSValue(bestValues, cbcAvailableValues)