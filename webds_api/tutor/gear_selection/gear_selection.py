import json
import math
import time
import sys, os
import numpy
import struct
import threading
from . import tunePDNR_covMat_v3
from ...touchcomm.touchcomm_manager import TouchcommManager

debug = True

def log(message):
    if debug:
        print(message)
    else:
        pass

def convert_chunk(i):
    return struct.unpack('<f', bytearray(i))[0]

def convert_to_float(i, n):
    for x in range(0, len(i), n):
        chunk = i[x:n+x]
        if len(chunk) < n:
            break
        yield convert_chunk(chunk)

class GearSelectionManager(object):
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(GearSelectionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, tc):
        log("GearSelectionManager")
        if GearSelectionManager._initialized:
            return
        self._thread = None
        self._stop_event = False
        self._tc = tc
        self._tcm = None
        self._total = 0
        self._progress = 0
        self._sweep = ""
        self._pdnr_index = 0
        self._pdnr_tuning = []
        self._noise_output = [[], [], []]
        GearSelectionManager._initialized = True

    def _set_static_config(self, static):
        self._tc.sendCommand(56)
        self._tc.getResponse()
        arg = self._tc.decoder.encodeStaticConfig(static)
        self._tc.sendCommand(57, arg)
        self._tc.getResponse()
        self._tc.sendCommand(55)
        self._tc.getResponse()
        time.sleep(0.1)

    def _set_dynamic_config(self, dynamic):
        self._tc.setDynamicConfig(dynamic)

    def _set_pdnr(self, static, basisAmpStdevTransRx, basisVectorsTransRx, basisAmpStdevAbsRx, basisVectorsAbsRx, basisAmpStdevAbsTx, basisVectorsAbsTx):
        static['ifpConfig.pdnrConfigs[0].basisAmpStdevTransRx'] = basisAmpStdevTransRx
        static['ifpConfig.pdnrConfigs[0].basisVectorsTransRx'] = basisVectorsTransRx
        static['ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx'] = basisAmpStdevAbsRx
        static['ifpConfig.pdnrConfigs[0].basisVectorsAbsRx'] = basisVectorsAbsRx
        static['ifpConfig.pdnrConfigs[0].basisAmpStdevAbsTx'] = basisAmpStdevAbsTx
        static['ifpConfig.pdnrConfigs[0].basisVectorsAbsTx'] = basisVectorsAbsTx

    def _set_pdnr_to_zeros(self, static):
        self._set_pdnr(static,
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisAmpStdevTransRx']),
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisVectorsTransRx']),
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx']),
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisVectorsAbsRx']),
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisAmpStdevAbsTx']),
                [0] * len(static['ifpConfig.pdnrConfigs[0].basisVectorsAbsTx']))

    def _set_trans_sensing_freqs(self, static, integDur, rstretchDur):
        static['integDur'][2] = integDur
        #static['daqParams.freqTable[2].rstretchDur'] = rstretchDur
        static['freqTable[2].rstretchDur'] = rstretchDur


    def _set_absTx_sensing_freqs(self, static, integDur, rstretchDur):
        static['integDur'][4] = integDur
        #static['daqParams.freqTable[4].rstretchDur'] = rstretchDur
        static['freqTable[4].rstretchDur'] = rstretchDur

    def _set_absRx_sensing_freqs(self, static, integDur, rstretchDur):
        static['integDur'][3] = integDur
        #static['daqParams.freqTable[3].rstretchDur'] = rstretchDur
        static['freqTable[3].rstretchDur'] = rstretchDur

    def set_trans_gears(self, gears, num_gears, commit):
        if not gears:
            return
        try:
            integDur = gears[0]
            rstretchDur = [0] * num_gears
            for idx in range(1, len(gears)):
                rstretchDur[idx] = gears[idx] - integDur
            self._tc.reset()
            self._tc.getAppInfo()
            static = self._tc.getStaticConfig()
            self._set_trans_sensing_freqs(static, integDur, rstretchDur)
            self._set_static_config(static)
            if commit:
                self._tc.commitConfig()
        except Exception as e:
            print("GearSelectionManager Exception (set_trans_gears): {}".format(e))

    def set_abs_gears(self, gears, num_gears, commit):
        if not gears:
            return
        try:
            integDur = gears[0]
            rstretchDur = [0] * num_gears
            for idx in range(1, len(gears)):
                rstretchDur[idx] = gears[idx] - integDur
            self._tc.reset()
            self._tc.getAppInfo()
            static = self._tc.getStaticConfig()
            self._set_absTx_sensing_freqs(static, integDur, rstretchDur)
            self._set_absRx_sensing_freqs(static, integDur, rstretchDur)
            self._set_static_config(static)
            if commit:
                self._tc.commitConfig()
        except Exception as e:
            print("GearSelectionManager Exception (set_abs_gears): {}".format(e))

    def clear_pdnr_tuning(self):
        self._pdnr_tuning = []
        self._pdnr_index = 0

    def pre_pdnr_sweep(self, int_durs, num_gears, baseline_frames, gram_data_frames):
        log("int_durs = {}, num_gears = {}, baseline_frames = {}, gram_data_frames = {}".format(int_durs, num_gears, baseline_frames, gram_data_frames))
        try:
            time.sleep(0.1)
            self._total = len(int_durs) * 3
            self._progress = 0
            self._sweep = "started"
            self._stop_event = False
            self._tc.reset()
            self._tc.getAppInfo()
            self._tc.enableReport(226)
            static = self._tc.getStaticConfig()
            self._set_pdnr_to_zeros(static)
            static['adnsEnabled'] = 1
            self._set_static_config(static)
            dynamic = self._tc.getDynamicConfig()
            dynamic['disableNoiseMitigation'] = 1
            dynamic['inhibitFrequencyShift'] = 1
            dynamic['requestedFrequency'] = 0
            dynamic['requestedFrequencyAbs'] = 0
            self._set_dynamic_config(dynamic)
            rx_count = static['rxCount']
            tx_count = static['txCount']
            self._pdnr_tuning.append([])
            covmat_cmd_arg = [baseline_frames & 0xff, (baseline_frames >> 8) & 0xff, gram_data_frames & 0xff, (gram_data_frames >> 8) & 0xff]
            for int_dur in int_durs:
                if self._stop_event:
                    self._tc.reset()
                    self._sweep = "stopped"
                    print(json.dumps({"state" : self._sweep}))
                    return
                raw_reports = []
                float_reports = []
                self._set_trans_sensing_freqs(static, int_dur, [0]*num_gears)
                self._set_absTx_sensing_freqs(static, int_dur, [0]*num_gears)
                self._set_absRx_sensing_freqs(static, int_dur, [0]*num_gears)
                self._set_static_config(static)
                self._tc.sendCommand(0xC3, covmat_cmd_arg)
                self._tc.getResponse()
                log('Received response to COMM_CMD_GET_PDNR_COVMAT')
                while True:
                    if self._stop_event:
                        self._tc.reset()
                        self._sweep = "stopped"
                        print(json.dumps({"state" : self._sweep}))
                        return
                    report = self._tc.getReport(600)
                    log(report)
                    raw_reports.append(report)
                    self._progress += 1
                    print(json.dumps({"progress": self._progress, "total": self._total}))
                    if len(raw_reports) >= 3:
                        break
                log('Received %d reports\n' % (len(raw_reports)))
                for report in raw_reports:
                    converted = list(convert_to_float(report[1][8:], 4))
                    #log(report)
                    log('Report index %d' % (report[1][0]))
                    log('%d data entries' % (len(converted)))
                    log(converted)
                    log('\n')
                    float_reports.append(converted)
                float_reports[0] = numpy.array(float_reports[0][0:rx_count*rx_count]).reshape(-1, rx_count)
                float_reports[1] = numpy.array(float_reports[1][0:rx_count*rx_count]).reshape(-1, rx_count)
                float_reports[2] = numpy.array(float_reports[2][0:20*20]).reshape(-1, 20)
                config = {
                    'updatePdnrConfigData': False,
                    'imageRxes': static['imageRxes'],
                    'adnsEnabled': static['adnsEnabled'],
                    'ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx': static['ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx']
                }
                pdnr = tunePDNR_covMat_v3.pdnrTuningFromCovMats(config, 1, gram_data_frames, tx_count, float_reports[0], float_reports[1], float_reports[2])
                pdnr['basisAmpStdevTransRx'] = [float(s) for s in pdnr['basisAmpStdevTransRx'].split(',')]
                pdnr['basisVectorsTransRx'] = [int(s) for s in pdnr['basisVectorsTransRx'].split(',')]
                pdnr['basisAmpStdevAbsRx'] = [float(s) for s in pdnr['basisAmpStdevAbsRx'].split(',')]
                pdnr['basisVectorsAbsRx'] = [int(s) for s in pdnr['basisVectorsAbsRx'].split(',')]
                pdnr['basisAmpStdevAbsTx'] = [float(s) for s in pdnr['basisAmpStdevAbsTx'].split(',')]
                pdnr['basisVectorsAbsTx'] = [int(s) for s in pdnr['basisVectorsAbsTx'].split(',')]
                self._pdnr_tuning[-1].append(pdnr)
            self._sweep = "completed"
            print(json.dumps({"state": "completed"}))
            self._tc.disableReport(226)
            log(self._pdnr_tuning)
        except Exception as e:
            print("GearSelectionManager Exception (pre_pdnr_sweep): {}".format(e))
            self._tc.disableReport(226)
            self._sweep = "stopped"
            print(json.dumps({"state" : self._sweep}))
            return

    def pdnr_sweep(self, int_durs, num_gears, baseline_frames, gram_data_frames):
        log("int_durs = {}, num_gears = {}, baseline_frames = {}, gram_data_frames = {}".format(int_durs, num_gears, baseline_frames, gram_data_frames))
        try:
            time.sleep(0.1)
            self._noise_output = [[], [], []]
            self._total = len(int_durs) * 3
            self._progress = 0
            self._sweep = "started"
            self._stop_event = False            
            self._tc.reset()
            self._tc.getAppInfo()
            self._tc.enableReport(226)
            static = self._tc.getStaticConfig()
            dynamic = self._tc.getDynamicConfig()
            dynamic['disableNoiseMitigation'] = 0
            dynamic['inhibitFrequencyShift'] = 1
            dynamic['requestedFrequency'] = 0
            dynamic['requestedFrequencyAbs'] = 0
            self._set_dynamic_config(dynamic)
            covmat_cmd_arg = [baseline_frames & 0xff, (baseline_frames >> 8) & 0xff, gram_data_frames & 0xff, (gram_data_frames >> 8) & 0xff]
            for idx, int_dur in enumerate(int_durs):
                if self._stop_event:
                    self._tc.reset()
                    self._sweep = "stopped"
                    print(json.dumps({"state" : "stopped"}))
                    return
                raw_reports = []
                self._set_pdnr(static,
                    self._pdnr_tuning[self._pdnr_index][idx]['basisAmpStdevTransRx'],
                    self._pdnr_tuning[self._pdnr_index][idx]['basisVectorsTransRx'],
                    self._pdnr_tuning[self._pdnr_index][idx]['basisAmpStdevAbsRx'],
                    self._pdnr_tuning[self._pdnr_index][idx]['basisVectorsAbsRx'],
                    self._pdnr_tuning[self._pdnr_index][idx]['basisAmpStdevAbsTx'],
                    self._pdnr_tuning[self._pdnr_index][idx]['basisVectorsAbsTx'])
                self._set_trans_sensing_freqs(static, int_dur, [0]*num_gears)
                self._set_absTx_sensing_freqs(static, int_dur, [0]*num_gears)
                self._set_absRx_sensing_freqs(static, int_dur, [0]*num_gears)
                static['forceFreshReport'] = 1
                self._set_static_config(static)
                self._tc.sendCommand(0xC3, covmat_cmd_arg)
                self._tc.getResponse()
                log('Received response to COMM_CMD_GET_PDNR_COVMAT')
                while True:
                    if self._stop_event:
                        self._tc.reset()
                        self._sweep = "stopped"
                        print(json.dumps({"state" : "stopped"}))
                        return  {"state": "stopped"}
                    report = self._tc.getReport(10)
                    raw_reports.append(report)
                    self._progress += 1
                    print(json.dumps({"progress": self._progress, "total": self._total}))
                    if len(raw_reports) >= 3:
                        break
                log('Received %d reports\n' % (len(raw_reports)))
                self._noise_output[0].append(next(convert_to_float(raw_reports[0][1][4:8], 4)))
                self._noise_output[1].append(next(convert_to_float(raw_reports[1][1][4:8], 4)))
                self._noise_output[2].append(next(convert_to_float(raw_reports[2][1][4:8], 4)))
            self._pdnr_index += 1
            time.sleep(0.1)
            self._sweep = "completed"
            self._tc.disableReport(226)
            log(self._noise_output)
            print(json.dumps({"state" : "completed", "reports" : self._noise_output}))
        except Exception as e:
            print("GearSelectionManager Exception (pdnr_sweep): {}".format(e))            
            self._tc.disableReport(226)
            self._sweep = "stopped"
            print(json.dumps({"state" : self._sweep}))
            return

    def get_noise_output(self):
        return self._noise_output

    def get_progress(self):
        return self._total, self._progress, self._sweep

    def reset_progress(self):
        self._noise_output = [[], [], []]
        self._total = 0
        self._progress = 0
        self._sweep = ""

    def join(self):
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def stop(self):
        self._stop_event = True

    def function(self, fn, args=None):
        log(fn)
        data = {}
        try:
            if args is None:
                data = getattr(self, fn)()
            else:
                if "sweep" in fn:
                    self._thread = threading.Thread(target=getattr(self, fn), args=args)
                    self._stop_event = False
                    self._thread.start()
                else:
                    data = getattr(self, fn)(*args)
        except Exception as e:
            print("GearSelectionManager Exception ({}): {}".format(fn, e))
            raise e
        return data
