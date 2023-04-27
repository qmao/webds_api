import sys
import re
import time
import json

CBC_POLARITY = 0x20
REPORT_ID = 31  ###195
CBC_AVAILABLE_VALUES = 63

def update_static_config(handle, config, config_to_set):
    try:
        for key in config_to_set:
            config_value = config_to_set[key]
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

def update_dynamic_config(handle, config, config_to_set):
    try:
        for key in config_to_set:
            config_value = config_to_set[key]
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

    def add(self, value):
        self._list.append(value)


class IntStatisticsSet():
    _count = 0
    _sum = 0
    _mean = 0
    _median = 0
    _min = sys.maxsize
    _max = -sys.maxsize - 1
    _min_of_max = sys.maxsize
    _max_of_min = -sys.maxsize - 1
    _sorted_data = SortedData()
    _local_min = sys.maxsize
    _local_max = -sys.maxsize - 1
    _subchannels = []

    def reset(self):
        self._count = 0
        self._sum = 0
        self._mean = 0
        self._median = 0
        self._min = sys.maxsize
        self._max = -sys.maxsize - 1
        self._min_of_max = sys.maxsize
        self._max_of_min = -sys.maxsize - 1
        self._sorted_data = SortedData()
        self._local_min = sys.maxsize
        self._local_max = -sys.maxsize - 1
        self._subchannels = []

    def __init__(self):
        self.reset()

    def process(self, data, perChannel=False):
        self._local_min = sys.maxsize
        self._local_max = -sys.maxsize - 1

        for i in range(len(data)):
            item = data[i]
            self._sorted_data.add(item)

            if perChannel:
                if i == len(self._subchannels):
                    obj = IntStatisticsSet()
                    self._subchannels.append(obj)

                sc = self._subchannels[i];
                sc.process([item])

            self._count = self._count + 1
            self._sum = self._sum + item;
            self._min = min(self._min, item)
            self._max = max(self._max, item)
            self._local_min = min(self._local_min, item)
            self._local_max = max(self._local_max, item)

        self._min_of_max = min(self._min_of_max, self._local_max)
        self._max_of_min = max(self._max_of_min, self._local_min)
        self._mean = (self._sum) / self._count
        self._median = self._sorted_data.get_median()

    def get_channels(self):
        return self._subchannels

    def get_median(self):
        return self._median

    def get_max(self):
        return self._max

    def get_min(self):
        return self._min

    def print_result(self):
        if False:
            print("Param: ", self._count, self._sum, self._min, self._max, self._local_min, self._local_max, self._min_of_max, self._max_of_min, self._mean, self._median)

class LocalCBC():
    _handle = None
    _start = None
    _debug = False
    _terminate = False
    _terminated = False
    _static_config = {}
    _dynamic_config = {}

    def __init__(self, handle):
        self._handle = handle
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
        ### low power mode
        if "requestedNoiseMode" in self._dynamic_config:
            self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"requestedNoiseMode": 5})
        else:
            print("requestedNoiseMode not found")

        self._dynamic_config = update_dynamic_config(self._handle, self._dynamic_config, {"noLowPower": 1})

        ### turn off analog-display noise suppression
        if "adnsEnabled" in self._static_config:
            self._static_config = update_static_config(self._handle, self._static_config, {"adnsEnabled": 0})


    def get_signal_clarity_type(self):
        if "signalClarityOrder" in self._touch_info:
            value = self._touch_info.get("signalClarityOrder", 0)
            return value >= 0
        return False

    def get_signal_clarity_enable(self):
        if "signalClarityOrder" in self._touch_info:
            if "signalClarityEnable" in self._static_config:
                value = self._static_config["signalClarityEnable"]
            elif "signalClarityIndex" in self._static_config:
                ##SWDS6-3176
                value = (self._static_config["signalClarityIndex"] != 0)
            else:
                raise Exception("signalClarityEnable config not found")
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

    def get_report(self, REPORT_ID):
        for i in range(5):
            try:
                report = self._handle.getReport()
                if report == ('timeout', None):
                    continue
                if report[0] == REPORT_ID:
                    ## print("data: ", ''.join('{:02x}'.format(x) for x in report[1]))
                    return report[1]
            except:
                pass
        raise Exception('cannot get valid report')

    def get_row(self, data, row, column):
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

    def run(self, samples_limit):
        self._terminated = self._terminate
        self.init()

        self.before_run()

        adc_range = 4096
        tx_count = self._static_config["txCount"]
        rx_count = self._static_config["rxCount"]
        num_buttons = self._app_info["numButtons"]

        try:
            signal_clarity_enable = self.get_signal_clarity_enable()
            cdm_order = self.get_signal_clarity_type()
        except Exception as e:
            self._terminated = True
            self.after_run()
            return {"data": e}

        if "imageBurstsPerCluster" in self._static_config:
            bursts_per_cluster = self._static_config["imageBurstsPerCluster"]
        elif "imageBurstsPerClusterQF" in self._static_config:
            bursts_per_cluster = self._static_config["imageBurstsPerClusterQF"]
        elif "imageBurstsPerClusterMF" in self._static_config:
            bursts_per_cluster = self._static_config["imageBurstsPerClusterMF"]

        realReportId = 0
        response = []
        numofsteps = int((CBC_AVAILABLE_VALUES + 1) / 2);
        step_percentage = 100 / (numofsteps * samples_limit)
        currentPercent = 0

        # item1 is best score, item 2 is index of best score
        best_scores = [[sys.maxsize, -1]] * rx_count
        polarity = [False] * rx_count

        self.print_time("Start")
        # 1. Set Image CBC for each enabled Rx to 0. 
        # For Gluon, setting CBC_CHn to 0 means that the local CBC for that channel is off.
        # There is no separate CBC_CARRIER_SEL value for each Rx.
        for step in range(numofsteps):
            array_ = [0] * rx_count
            for index in range(rx_count):
                value = 0x00
                if polarity[index]:
                    value = CBC_POLARITY
                array_[index] = step | value
            self.update_image_cbcs(array_)
            self.print_time("update_image_cbcs")

            status = self.set_report(True, REPORT_ID)
            self.print_time("set_report")

            if status == False:
                print("transaction failed")
                raise Exception('set_report transaction failed')

            if self._terminate:
                print("user terminate")
                break

            currentPercent = step * samples_limit * step_percentage;
            print(json.dumps({"state": "run", "progress": currentPercent}))

            samples = []
            # start data collecting
            for samples_collected in range(samples_limit):
                ###print("LOOP:", step, samples_collected)
                if self._terminate:
                    print("user terminate")
                    break

                data = self.get_report(REPORT_ID)
                self.print_time("get_report")

                samples.append(data)
                progress = currentPercent + (samples_collected * step_percentage)
                print(json.dumps({"state": "run", "progress": progress}))

            # stop data collecting
            status = self.set_report(False, REPORT_ID)
            self.print_time("set_report disable")

            # Calculate stats
            statistics_set = IntStatisticsSet()

            for sample in samples:
                if len(sample) == 0:
                    raise Exception('cannot get valid report')
                rows = self.get_row(sample, rx_count, tx_count)
                for row in rows:
                    statistics_set.process(row, True)

            # Calculate the best scores
            statistics_rows = statistics_set.get_channels()

            for idx, i in enumerate(statistics_rows):
                if step is 0:
                    if i.get_max() < 3000:
                        adc_range = 2048

                i.print_result()

                lmin = i.get_min()
                lmax = i.get_max()
                ## intvar = i.get_median()
                ## score = (intvar - 4096) / bursts_per_cluster    # Juneau Specific - 13bit ADC (SWDS6-3161)

                score_next = 0
                score_prev = 0
                if idx is not 0:
                    score_prev = abs((statistics_rows[idx - 1].get_max() - adc_range) - (adc_range - statistics_rows[idx - 1].get_min()))
                if idx is not (rx_count -1):
                    score_next = abs((statistics_rows[idx + 1].get_max() - adc_range) - (adc_range - statistics_rows[idx + 1].get_min()))
                score = abs((lmax - adc_range) - (adc_range - lmin)) + score_prev + score_next

                if abs(score) < abs(best_scores[idx][0]):
                    best_scores[idx] = [score, step]
            if self._debug:
                print("BEST SCORE: ", best_scores)

            # 5.For CBC off (== 0) For each receiver, if Score is positive, 
            # set CBC TX Pl for that receiver = 0 (charge subtraction). 
            # If Score is negative, set CBC TX Pl for that receiver = 1 (charge addition).
            if step == 0:
                for i in range(rx_count):
                    if best_scores[i][0] < 0:
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
        best_values = [0] * len(best_scores)

        for idx, i in enumerate(best_scores):
            best_values[idx] = i[1]
            if best_values[idx] != 0:
                if polarity[idx]:
                    best_values[idx] = best_values[idx] | CBC_POLARITY
                else:
                    best_values[idx] = best_values[idx] & ~CBC_POLARITY

        print("[Best]: ", best_values)

        self.after_run()
        self.update_image_cbcs(best_values)

        print(json.dumps({"state": "run", "progress": 100}))
        return self.convert_cbcs_value(best_values, CBC_AVAILABLE_VALUES)

    def terminate(self):
        self._terminate = True
        while True:
            if self._terminated:
                break
            time.sleep(0.005)
        print("Terminated!")