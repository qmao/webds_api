import sys
import re
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..configuration.config_handler import ConfigHandler

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
                sc.Process([item]);

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
        print("Param1: ", self._Count, self._Sum, self._Min, self._Max, self._LocalMin, self._LocalMax)
        print("Param2: ", self._MinOfMax, self._MaxOfMin, self._Mean, self._Median)

class LocalCBC():
    _tc = None

    def __init__(self):
        self._tc = TouchcommManager()

    def getSignalClarityType(self):
        return 1
        if signalClarityOrder in data:
            value = data["signalClarityOrder"]
            return value >= 0
        return False

    def getSignalClarityEnable(self):
        return True
        if signalClarityOrder in data:
            value = data["signalClarityEnable"]
            return value
        return False

    def init(self):
        self._tc.disableReport(17)
        self._tc.disableReport(18)
        self._tc.disableReport(19)
        self._tc.disableReport(20)

    def convertInt16ToData(self, x):
      data = [0, 0]
      data[0] = x & 0xFF;
      data[1] = (x >> 8) & 0xFF;
      return data

    def updateImageCBCs(self, data):
        config = ConfigHandler._update_static_config({"imageCBCs": data}, self._tc)

    def setReport(self, enable, report):
        if enable:
            ret = self._tc.enableReport(report)
        else:
            ret = self._tc.disableReport(report)
        return True

    def getReport(self):
        for i in range(5):
            try:
                report = self._tc.getReport()
                if report == ('timeout', None):
                    continue
                if report[0] == 31:
                    return report[1]
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

    def convertCBCSValue(self, data, count):
        base = (count + 1) / 2 

        arr = []
        for i in data:
            value = 0
            if i < base:
               value = abs(i - base + 1) * 0.5
            else:
               value = 0 - ((i - base) * 0.5)
            print(i, "=>",value)
            arr.append(value)
        return arr

    def run(self):
        self.init()
        ### global
        _CBC_flagPolarity = 0x20
        terminate = False

        reportId = 31  ###195
        cbcAvailableValues = 63
        samplesLimit = 10
        txCount = 18
        rxCount = 40
        numButtons = 0
        signalClarityEnabled = self.getSignalClarityEnable()
        cdmOrder = self.getSignalClarityType()
        burstsPerCluster = 1

        realReportId = 0
        response = []
        numofsteps = int((cbcAvailableValues + 1) / 2);
        stepPercentage = 100 / (numofsteps * samplesLimit);
        currentPercent = 0;

        ##print("Progress param:", numofsteps, samplesLimit, stepPercentage)

        # item1 is best score, item 2 is index of best score
        bestScores = [[sys.maxsize, -1]] * rxCount
        polarity = [False] * rxCount

        ##print(bestScores, polarity)

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

            status = self.setReport(True, reportId)
            if status:
                print("transaction success")
            else:
                print("transaction failed")

            if terminate:
                print("user terminate")
                break

            currentPercent = step * samplesLimit * stepPercentage;
            print(currentPercent)

            samples = []
            # start data collecting
            for samplesCollected in range(samplesLimit):
                ###print("LOOP:", step, samplesCollected)
                if terminate:
                    print("user terminate")
                    break

                data = self.getReport()

                samples.append(data)
                progress = currentPercent + (samplesCollected * stepPercentage)

            # stop data collecting
            status = self.setReport(False, reportId)

            # Calculate stats
            statisticsSet = IntStatisticsSet()

            for sample in samples:
                if len(sample) == 0:
                    raise Exception('cannot get valid report')
                rows = self.getRow(sample, rxCount, txCount, numButtons, cdmOrder)
                for row in rows:
                    statisticsSet.Process(row, True);

            # Calculate the best scores
            statisticsRows = statisticsSet.GetChannels()

            for idx, i in enumerate(statisticsRows):
                ###i.printResult()
                intvar = i.GetMedian()

                score = (intvar - 4096) / burstsPerCluster    # Juneau Specific - 13bit ADC (SWDS6-3161)
                if abs(score) < abs(bestScores[idx][0]):
                    bestScores[idx] = [score, step]

            #print("BEST SCORE: ", bestScores)

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

        print("[Best]: ", bestValues)
        return self.convertCBCSValue(bestValues, cbcAvailableValues)