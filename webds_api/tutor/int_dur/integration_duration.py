import threading
import time
import math
from statistics import mean
from ..tutor_utils import SSEQueue
from ...touchcomm.touchcomm_manager import TouchcommManager

debug = True

SFTYPE_TRANS = 2
ISTRETCH_DUR = 5
STRETCH_INDEX = 0
PARAM_INT_DUR = "integDur"
PARAM_RSTRETCH_DUR = "freqTable[0].rstretchDur"
PARAM_ISTRETCH_DUR = "freqTable[0].stretchDur"

I0 = 21
SAMPLE_DUR = 7
INT_DUR_FLOOR = 10
OVERHEAD_DUR = 10
MID_FIRST_SENSE_DUR = 10

SIGNAL_SETTLING = 0.9
BASELINE_MARGIN = 0.2
MAX_SLOPE_FACTOR = 1.2
I0_ADJUSTMENT_FACTOR = 1.5

LEVELS = 3
RETRIES = 4
SAMPLE_SIZE = 30

SSE_EVENT = "integration_duration"

def log(message):
    if debug:
        print(message)
    else:
        pass

class IntegrationDuration(object):
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(IntegrationDuration, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        log("IntegrationDuration")

        if IntegrationDuration._initialized:
            return

        self._thread = None
        self._stop_event = False
        self._tc = None
        self._tcm = None
        self._queue = SSEQueue()
        self._static_config = {}
        self._dynamic_config = {}
        self._inited = False
        self._row = ""
        self._col = ""
        self._case = 0
        self._min_int_dur = 0
        self._test_pixels = []
        self._tuning_settings = []
        self._test_pixel_baseline_raw = []
        self._test_pixel_baseline_max = []
        self._test_pixel_baseline_min = []
        self._test_pixel_baseline_mean = []
        self._test_pixel_signal_raw = []
        self._test_pixel_signal_max = []
        self._test_pixel_signal_min = []
        self._test_pixel_signal_mean = []

        IntegrationDuration._initialized = True

    def _connect_tc(self):
        self._tcm = TouchcommManager()
        self._tc = self._tcm.getInstance()

    def _disconnect_tc(self):
        if self._tcm is not None:
            self._tcm.disconnect()
            self._tcm = None

    def _update_progress(self, progress):
        self._queue.setInfo(SSE_EVENT, {"state": "running", "progress": progress})

    def _set_static_config(self):
        self._tc.setStaticConfig(self._static_config)

    def _set_dynamic_config(self):
        self._tc.setDynamicConfig(self._dynamic_config)

    def _get_min_int_dur(self):
        nlp_trx_sel = 1
        nlp_lcbc_sel = 1

        trx_duration = self._static_config["tchXmtrCtrl1[{}].trxMidDur".format(SFTYPE_TRANS)] + self._static_config["tchXmtrCtrl1[{}].trxMidDur2".format(SFTYPE_TRANS)] + 2 * nlp_trx_sel
        lcbc_duration = self._static_config["tchCbcCtl[{}].lcbcMidDur".format(SFTYPE_TRANS)] + self._static_config["tchCbcCtl2[{}].lcbcMidDur2".format(SFTYPE_TRANS)] + 2 * nlp_lcbc_sel

        max_duration = max(trx_duration, lcbc_duration)
        min_duration = SAMPLE_DUR - MID_FIRST_SENSE_DUR - 1

        return max_duration - min_duration + 1

    def _get_tuning_settings(self):
        tuning_settings = []
        int_dur = -SAMPLE_DUR

        for _ in range(LEVELS):
            int_dur += I0
            rstretch_dur = 0 if int_dur >= INT_DUR_FLOOR else INT_DUR_FLOOR - int_dur
            int_dur = self._min_int_dur if int_dur < self._min_int_dur else int_dur
            tuning_settings.append((int_dur, rstretch_dur))

        return tuning_settings

    def _get_derated_min_int_dur(self, int_dur):
        return math.floor(((int_dur + OVERHEAD_DUR) * (1 + BASELINE_MARGIN)) - OVERHEAD_DUR)

    def _get_tau_a_d(self, int_dur0, int_dur1, delta):
        if delta[0] >= delta[1]:
            tau = self._get_derated_min_int_dur(int_dur0)
            big_a = None
            big_d = None
            self._case = 1
        elif delta[1] >= delta[2]:
            tau = (int_dur0 + OVERHEAD_DUR) / math.log(delta[1] / (delta[1] - delta[0]))
            big_a = delta[2]
            big_d = 0
            self._case = 2
        elif (delta[2] - delta[1]) >= (delta[1] - delta[0]):
            tau = (int_dur0 + OVERHEAD_DUR) / math.log(delta[1] / (delta[2] - delta[0]))
            temp1 = math.exp(-(int_dur0 + OVERHEAD_DUR) / tau)
            temp2 = 1 - math.exp(-(int_dur1 + OVERHEAD_DUR) / tau)
            big_a = (delta[2] - delta[0]) / (temp1 * temp2)
            big_d = 0
            self._case = 3
        else:
            tau = (int_dur0 + OVERHEAD_DUR) / math.log((delta[1] - delta[0])/ (delta[2] - delta[1]))
            temp1 = math.exp(-(int_dur0 + OVERHEAD_DUR) / tau)
            temp2 = 1 - math.exp(-(int_dur0 + OVERHEAD_DUR) / tau)
            big_a = (delta[1] - delta[0]) / (temp1 * temp2)
            big_d = delta[0] - (big_a * temp2)
            self._case = 4
        return tau, big_a, big_d

    def _get_optimal_int_dur(self, min_int_dur, max_int_dur, tau, big_a, big_d):
        if self._case == 1:
            return min_int_dur, True
        optimal = False
        for int_dur in range(min_int_dur, max_int_dur + 1):
            perturbed_int_dur = math.floor((int_dur + OVERHEAD_DUR) / (1 + BASELINE_MARGIN))
            nominal_delta = big_a * (1 - math.exp(-1 * (int_dur + OVERHEAD_DUR) / tau)) + big_d
            perturbed_delta = big_a * (1 - math.exp(-1 * perturbed_int_dur / tau)) + big_d
            ratio = perturbed_delta / nominal_delta
            if ratio >= SIGNAL_SETTLING:
                optimal = True
                break
        if optimal == False and self._case == 2:
            int_dur = self._get_derated_min_int_dur(self._tuning_settings[1][0])
            optimal = True
        return int_dur, optimal

    def initialize(self, test_pixels):
        log("Initializing")
        try:
            self._connect_tc()
            self._tc.reset()
            time.sleep(0.5)

            self._static_config = self._tc.getStaticConfig()
            self._static_config["adnsEnabled"] = 0
            self._static_config[PARAM_ISTRETCH_DUR][STRETCH_INDEX] = ISTRETCH_DUR
            self._set_static_config()

            self._dynamic_config = self._tc.getDynamicConfig()
            self._dynamic_config["noLowPower"] = 1
            self._set_dynamic_config()

            self._row = "tx" if self._static_config["txAxis"] == 1 else "rx"
            self._col = "rx" if self._row == "tx" else "tx"

            self._test_pixels = test_pixels
            self._min_int_dur = self._get_min_int_dur()

            self._inited = True

            log("\nInitialized")
        except Exception as e:
            print("IntegrationDuration error executing initialize: {}".format(e))
            self._disconnect_tc()
            raise e

    def collect_baseline_data(self):
        log("Collecting baseline data")
        self._update_progress(10)
        try:
            if not self._inited:
                self.initialize()
            self._connect_tc()
            time.sleep(0.5)
            self._tc.disableReport(17)
            self._tc.disableReport(18)
            self._tc.disableReport(19)
            self._tc.disableReport(20)
            progress = 0
            total = LEVELS * SAMPLE_SIZE
            valid_baseline = False
            for attemp in range(RETRIES):
                log("Attemp {}".format(attemp + 1))
                slowest_index = 0
                self._test_pixel_baseline_raw = [[[] for _ in range(len(self._test_pixels))] for _ in range(LEVELS)]
                self._test_pixel_baseline_max = [[] for _ in range(LEVELS)]
                self._test_pixel_baseline_min = [[] for _ in range(LEVELS)]
                self._test_pixel_baseline_mean = [[] for _ in range(LEVELS)]
                self._tuning_settings = self._get_tuning_settings()
                for level in range(LEVELS):
                    int_dur, rstretch_dur = self._tuning_settings[level]
                    log("Integration duration = {}, Rstretch duration = {}".format(int_dur, rstretch_dur))
                    self._static_config[PARAM_INT_DUR][SFTYPE_TRANS] = int_dur
                    self._static_config[PARAM_RSTRETCH_DUR][STRETCH_INDEX] = rstretch_dur
                    self._set_static_config()
                    self._tc.enableReport(19)
                    count = 0
                    while True:
                        if self._stop_event:
                            self._queue.setInfo(SSE_EVENT, {"state": "terminate"})
                            return
                        report = self._tc.getReport()
                        if report[0] == "raw":
                            count += 1
                            progress += 1
                            self._update_progress(progress / total * 90 + 10)
                            report = report[1]["image"]
                            for pixel, data in enumerate(self._test_pixels):
                                r = data["pixel"][self._row]
                                c = data["pixel"][self._col]
                                self._test_pixel_baseline_raw[level][pixel].append(report[r][c])
                        if count >= SAMPLE_SIZE:
                            break
                    self._tc.disableReport(19)
                    for data in self._test_pixel_baseline_raw[level]:
                        self._test_pixel_baseline_max[level].append(max(data))
                        self._test_pixel_baseline_min[level].append(min(data))
                        self._test_pixel_baseline_mean[level].append(round(mean(data)))
                    log("Max = {}".format(self._test_pixel_baseline_max[level]))
                    log("Min = {}".format(self._test_pixel_baseline_min[level]))
                    log("Mean = {}".format(self._test_pixel_baseline_mean[level]))
                    if level == 0:
                        slowest_index = min(range(len(self._test_pixel_baseline_min[level])), key=self._test_pixel_baseline_min[level].__getitem__)
                        log("Slowest index = {}".format(slowest_index))
                if self._test_pixel_baseline_mean[2][slowest_index] > MAX_SLOPE_FACTOR * self._test_pixel_baseline_mean[1][slowest_index]:
                    I0 = math.floor(I0 * I0_ADJUSTMENT_FACTOR)
                else:
                    valid_baseline = True
                    break
            if not valid_baseline:
                raise RuntimeError("no valid baseline found")
            self._queue.setInfo(SSE_EVENT, {"state": "stop"})
            log("Collected baseline data")
            return
        except Exception as e:
            print("IntegrationDuration error executing collect_baseline_data: {}".format(e))
            self._queue.setInfo(SSE_EVENT, {"state": "terminate"})
            self._disconnect_tc()
            self._inited = False
            raise e

    def collect_test_pixel_data(self, pixel):
        log("Collecting test pixel {} data".format(pixel))
        self._update_progress(10)
        try:
            if not self._inited:
                self.initialize()
            self._connect_tc()
            time.sleep(0.5)
            self._tc.disableReport(17)
            self._tc.disableReport(18)
            self._tc.disableReport(19)
            self._tc.disableReport(20)
            progress = 0
            total = LEVELS * SAMPLE_SIZE
            if pixel == 0:
                self._test_pixel_signal_raw = [[[] for _ in range(len(self._test_pixels))] for _ in range(LEVELS)]
                self._test_pixel_signal_max = [[] for _ in range(LEVELS)]
                self._test_pixel_signal_min = [[] for _ in range(LEVELS)]
                self._test_pixel_signal_mean = [[] for _ in range(LEVELS)]
            for level in range(LEVELS):
                int_dur, rstretch_dur = self._tuning_settings[level]
                log("Integration duration = {}, Rstretch duration = {}".format(int_dur, rstretch_dur))
                self._static_config[PARAM_INT_DUR][SFTYPE_TRANS] = int_dur
                self._static_config[PARAM_RSTRETCH_DUR][STRETCH_INDEX] = rstretch_dur
                self._set_static_config()
                self._tc.enableReport(19)
                count = 0
                while True:
                    if self._stop_event:
                        self._queue.setInfo(SSE_EVENT, {"state": "terminate"})
                        return
                    report = self._tc.getReport()
                    if report[0] == "raw":
                        count += 1
                        progress += 1
                        self._update_progress(progress / total * 90 + 10)
                        report = report[1]["image"]
                        r = self._test_pixels[pixel]["pixel"][self._row]
                        c = self._test_pixels[pixel]["pixel"][self._col]
                        self._test_pixel_signal_raw[level][pixel].append(report[r][c])
                    if count >= SAMPLE_SIZE:
                        break
                self._tc.disableReport(19)
                self._test_pixel_signal_max[level].append(max(self._test_pixel_signal_raw[level][pixel]))
                self._test_pixel_signal_min[level].append(min(self._test_pixel_signal_raw[level][pixel]))
                self._test_pixel_signal_mean[level].append(round(mean(self._test_pixel_signal_raw[level][pixel])))
                log("Max = {}".format(self._test_pixel_signal_max[level][-1]))
                log("Min = {}".format(self._test_pixel_signal_min[level][-1]))
                log("Mean = {}".format(self._test_pixel_signal_mean[level][-1]))
            self._queue.setInfo(SSE_EVENT, {"state": "stop"})
            log("Collected test pixel {} data".format(pixel))
            return
        except Exception as e:
            print("IntegrationDuration error executing collect_test_pixel_data: {}".format(e))
            self._queue.setInfo(SSE_EVENT, {"state": "terminate"})
            self._disconnect_tc()
            self._inited = False
            raise e

    def get_results(self):
        try:
            delta = [[abs(a - b) for a, b in zip(b, s)] for b, s in zip(self._test_pixel_baseline_mean, self._test_pixel_signal_mean)]
            log("\nDelta = {}".format(delta))
            test_pixel_delta = []
            test_pixel_tau_a_d = []
            for pixel in range(len(self._test_pixels)):
                test_pixel_delta.append([d[pixel] for d in delta])
                test_pixel_tau_a_d.append(self._get_tau_a_d(self._tuning_settings[0][0], self._tuning_settings[1][0], test_pixel_delta[pixel]))
            log("Test pixel delta = {}".format(test_pixel_delta))
            log("Test pixel tau a d = {}".format(test_pixel_tau_a_d))
            taus = [tad[0] for tad in test_pixel_tau_a_d]
            max_tau_index = max(range(len(taus)), key=taus.__getitem__)
            tau = test_pixel_tau_a_d[max_tau_index][0]
            big_a = test_pixel_tau_a_d[max_tau_index][1]
            big_d = test_pixel_tau_a_d[max_tau_index][2]
            log("Tau = {}, A = {}, D = {}".format(tau, big_a, big_d))
            minimum_int_dur = self._get_derated_min_int_dur(self._tuning_settings[0][0])
            optimal_int_dur = self._get_optimal_int_dur(minimum_int_dur, 1023, tau, big_a, big_d)
            log("Optimal integration duration = {}".format(optimal_int_dur))
            return {"tau": tau, "bigA": big_a, "bigD": big_d, "minimumIntDur": minimum_int_dur, "optimalIntDur": optimal_int_dur}
        except Exception as e:
            print("IntegrationDuration error executing get_results: {}".format(e))
            raise e

    def join(self):
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def cancel_data_collection(self):
        self._stop_event = True
        self.join()

    def function(self, fn, args=None):
        log("\n{}".format(fn))
        retval = None
        try:
            if "collect" in fn:
                if args is None:
                    self._thread = threading.Thread(target=getattr(self, fn))
                else:
                    self._thread = threading.Thread(target=getattr(self, fn), args=args)
                self._stop_event = False
                self._thread.start()
            elif args is None:
                retval = getattr(self, fn)()
            else:
                retval = getattr(self, fn)(*args)
        except Exception as e:
            print("IntegrationDuration error executing {}: {}".format(fn, e))
            raise e
        return retval
