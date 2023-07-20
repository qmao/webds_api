from __future__ import division
import json
import math
import threading
import time
from pprint import pprint

SFTYPE_NOISE = 1
SFTYPE_TRANS = 2
SFTYPE_ABSRX = 3
SFTYPE_ABSTX = 4
SFTYPE_ABSNB = 5
SFTYPE_PMFNB = 6

STATE_TRANS_QF = 0
STATE_TRANS_MF = 1
STATE_HYBRID_X =2
STATE_HYBRID_Y = 3
NUM_STATES = 4

SAMPLE_DURATION = 7
OTHER_OVERHEAD = 3
EXT_OSC_CLOCK = 32
INTER_OSC_CLOCK = 29

FTAC = 29E6
SETUP_TIME = 1.43E-6
HARD_RESET_DUR = 186/FTAC + SETUP_TIME
STALL_TIME = 412.8E-6
FILTER_BANDWIDTH_MAX = 15

VAL_INVALID = float('-inf')
debug = False

def log(message):
    if debug:
        print(message)
    else:
        pass

class FrameTiming(object):
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(FrameTiming, cls).__new__(cls)
        return cls._instance

    def __init__(self, tc):
        if FrameTiming._initialized:
            return
                 
        self._freq_inited = False
        self._tc = tc

        self._num_gears = 0
        self._target_timing_freq_qf = []
        self._default_timing_freq_qf = []
        self._max_timing_freq_qf = VAL_INVALID

        self._target_timing_freq_mf = []
        self._default_timing_freq_mf = []       
        self._max_timing_freq_mf = VAL_INVALID

        self._target_timing_freq_hybrid = []
        self._default_timing_freq_hybrid = []        
        self._max_timing_freq_hybrid = VAL_INVALID        
        self._timing_max = VAL_INVALID

        self._list_results_noise_trans_qf = []
        self._list_results_noise_trans_mf = []
        self._list_results_noise_hybrid_x = []
        self._list_results_noise_hybrid_y = []

        self._target_timing_rate = 120
        self._tuning_strategy = 1 
        FrameTiming._initialized = True

    def frame_timing_init(self):
        try:
            return self._initialize()
        except Exception as e:
            print("error: {}".format(e))
            self._freq_inited = False
            raise e

    def frame_timing_calculate(self, target_freq_trans , target_freq_hybrid, target_report_rate, tuning_strategy):
        try:
            if not self._freq_inited:
                self._initialize()

            self._target_timing_rate = int(target_report_rate)
            self._tuning_strategy = int(tuning_strategy)
            self._has_constant_noise = (self._tuning_strategy == 0) # just calculate, no optimization
            self._has_power_noise = (self._tuning_strategy == 1); #minimum power
            self._target_timing_freq_qf = target_freq_trans
            self._target_timing_freq_mf = target_freq_trans
            self._target_timing_freq_hybrid = target_freq_hybrid
            list_usage_noise_qf = [True, True, True, True]
            list_usage_noise_mf = [True, True, True, True]
            list_usage_noise_hybrid = [True, True, True, True]
            calculate_reslut = {}
            for state in range(NUM_STATES):
                if state == STATE_TRANS_QF:
                    self._list_results_noise_trans_qf = self._calculate_noise_gear_results(self._target_timing_freq_qf, list_usage_noise_qf, state)
                    for result in self._list_results_noise_trans_qf:
                        self._update_value(result)
                        if debug:
                            pprint(vars(result.gear_quiet))
                            pprint(vars(result.gear_multi))
                    calculate_reslut['STATE_TRANS_QF'] = self._generate_gear_result_json(self._list_results_noise_trans_qf)
                elif state == STATE_TRANS_MF:
                    self._list_results_noise_trans_mf = self._calculate_noise_gear_results(self._target_timing_freq_mf, list_usage_noise_mf, state)
                    for result in self._list_results_noise_trans_mf:
                        self._update_value(result)
                        if debug:
                            pprint(vars(result.gear_quiet))
                            pprint(vars(result.gear_multi))
                    calculate_reslut['STATE_TRANS_MF'] = self._generate_gear_result_json(self._list_results_noise_trans_mf)
                elif state == STATE_HYBRID_X:
                    self._list_results_noise_hybrid_x = self._calculate_noise_gear_results(self._target_timing_freq_hybrid, list_usage_noise_hybrid, state)
                    for result in self._list_results_noise_hybrid_x:
                        self._update_value(result)
                        if debug:
                            pprint(vars(result.gear_quiet))
                            pprint(vars(result.gear_multi))
                    calculate_reslut['STATE_HYBRID_X'] = self._generate_gear_result_json(self._list_results_noise_hybrid_x)                                               
                elif state == STATE_HYBRID_Y:
                    self._list_results_noise_hybrid_y = self._calculate_noise_gear_results(self._target_timing_freq_hybrid, list_usage_noise_hybrid, state)
                    for result in self._list_results_noise_hybrid_y:
                        self._update_value(result)
                        if debug:
                            pprint(vars(result.gear_quiet))
                            pprint(vars(result.gear_multi))
                    calculate_reslut['STATE_HYBRID_Y'] = self._generate_gear_result_json(self._list_results_noise_hybrid_y)  

            return calculate_reslut           
        except Exception as e:
            print("error: {}".format(e))
            raise e

    def update_gear_usage(self, state, gear_idx, freq_type, usage):
        try:
            if not self._is_calculation_completed:
                raise RuntimeError("Frame timing results haven't been generated successfully")

            temp_list_results = []
            state_idx = 0
            if state == 'STATE_TRANS_QF':
                temp_list_results = self._list_results_noise_trans_qf
                state_idx = STATE_TRANS_QF
            elif state == 'STATE_TRANS_MF':
                temp_list_results = self._list_results_noise_trans_mf
                state_idx = STATE_TRANS_MF
            elif state == 'STATE_HYBRID_X':
                temp_list_results = self._list_results_noise_hybrid_x
                state_idx = STATE_HYBRID_X
            elif state == 'STATE_HYBRID_Y':
                temp_list_results = self._list_results_noise_hybrid_y
                state_idx = STATE_HYBRID_Y

            if gear_idx >= len(temp_list_results):
                raise RuntimeError("Incorrect Gear Number")

            if temp_list_results is not None:
                if freq_type == 'quiet':
                    temp_list_results[gear_idx].gear_quiet.is_used = usage
                    if not self._enable_results(temp_list_results, True, False, state_idx) or \
                        not self._update_results(temp_list_results, state_idx):
                        raise RuntimeError("Failed to update QF gear usage")
                else:
                    temp_list_results[gear_idx].gear_multi.is_used = usage
                    if not self._enable_results(temp_list_results, False, True, state_idx) or \
                        not self._update_results(temp_list_results, state_idx):
                        raise RuntimeError("Failed to update MF gear usage")

            if state_idx == STATE_TRANS_QF:
                self._list_results_noise_trans_qf = temp_list_results
            elif state_idx == STATE_TRANS_MF:
                self._list_results_noise_trans_mf = temp_list_results
            elif state_idx == STATE_HYBRID_X:
                self._list_results_noise_hybrid_x = temp_list_results
            elif state_idx == STATE_HYBRID_Y:
                self._list_results_noise_hybrid_y = temp_list_results

            update_reslut = {}
            update_reslut['STATE_TRANS_QF'] = self._generate_gear_result_json(self._list_results_noise_trans_qf)
            update_reslut['STATE_TRANS_MF'] = self._generate_gear_result_json(self._list_results_noise_trans_mf)
            update_reslut['STATE_HYBRID_X'] = self._generate_gear_result_json(self._list_results_noise_hybrid_x)
            update_reslut['STATE_HYBRID_Y'] = self._generate_gear_result_json(self._list_results_noise_hybrid_y)
            return update_reslut
        except Exception as e:
            print("error: {}".format(e))
            raise e

    def set_timing_variables(self, commit):
        if not self._is_calculation_completed:
            return            
        try:
            self._tc.reset()
            self._tc.getAppInfo()
            static = self._tc.getStaticConfig()
            for state in range(NUM_STATES):
                if state == STATE_TRANS_QF:
                    for gear_idx, result in enumerate(self._list_results_noise_trans_qf):
                        self._set_timing_variables(static, result.gear_quiet.variables_table[state], gear_idx)
                elif state == STATE_TRANS_MF:
                    for gear_idx, result in enumerate(self._list_results_noise_trans_mf):
                        self._set_timing_variables(static, result.gear_multi.variables_table[state], gear_idx)
                elif state == STATE_HYBRID_X:
                    for gear_idx, result in enumerate(self._list_results_noise_hybrid_x):
                        self._set_timing_variables(static, result.gear_quiet.variables_table[state], gear_idx)
                        self._set_timing_variables(static, result.gear_multi.variables_table[state], gear_idx)
                elif state == STATE_HYBRID_Y:
                    for gear_idx, result in enumerate(self._list_results_noise_hybrid_y):
                        self._set_timing_variables(static, result.gear_quiet.variables_table[state], gear_idx)
                        self._set_timing_variables(static, result.gear_multi.variables_table[state], gear_idx)
            self._set_static_config(static)
            if commit:
                self._tc.commitConfig()
        except Exception as e:
            print("Failed to save frame timing variables: {}".format(e))

    def _initialize(self):
        try:
            self._default_timing_freq_qf.clear()
            self._default_timing_freq_mf.clear()
            self._default_timing_freq_hybrid.clear()
            self._static_config = self._tc.getStaticConfig()
            self._tc.reset()
            time.sleep(0.5)

            self._static_config = self._tc.getStaticConfig()
            self._sample_duration = self._static_config['AnalogTuning.sampleDuration'] \
                  if 'AnalogTuning.sampleDuration' in self._static_config else SAMPLE_DURATION
            self._other_overhead = self._static_config['AnalogTuning.OtherOverhead'] \
                  if 'AnalogTuning.sampleDuration' in self._static_config else OTHER_OVERHEAD

            self._num_gears = len(self._static_config['freqTable[0].disableFreq'])
            self._param_frame = FrameTimingParameters(**self._static_config)

            # create the initial, using smallest stretch-duration
            gear_frame = self._get_first_freq_gear()            
            success, freq_frame = self._get_frame_freq(gear_frame, STATE_TRANS_QF)
            if not success:
                raise RuntimeError("Failed to get trans QF frequency")

            frame_filter_bandwidth = self._get_frame_filter_bandwidth(freq_frame)
            self._set_gear_table_variables(gear_frame, frame_filter_bandwidth)
            success, frame_time = self._get_quiet_frame_time(gear_frame)
            if success:
                self._timing_max = math.floor((1/frame_time) * 1E6)

            frame_freq = VAL_INVALID
            self._set_gear_table_variables(gear_frame, 15)
            for state in range(NUM_STATES - 1):
                if state == STATE_TRANS_QF:
                    success, frame_freq = self._get_frame_freq(gear_frame, STATE_TRANS_QF)
                    if not success:
                        raise RuntimeError("Failed to get trans QF frequency")
                    self._max_timing_freq_qf = round(frame_freq, 2)
                elif state == STATE_TRANS_MF:          
                    success, frame_freq = self._get_frame_freq(gear_frame, STATE_TRANS_MF)
                    if not success:
                        raise RuntimeError("Failed to get trans MF frequency")
                    self._max_timing_freq_mf = round(frame_freq, 2)             
                elif state == STATE_HYBRID_X:          
                    success, frame_freq = self._get_frame_freq(gear_frame, STATE_HYBRID_X)
                    if not success:
                        raise RuntimeError("Failed to get Hybrid frequency")
                    self._max_timing_freq_hybrid = round(frame_freq, 2)               
                for gear_idx in range(self._num_gears):
                    if state == STATE_TRANS_QF:
                        gear_frame_qf = FrameTimingGear(True, False)
                        gear_frame_qf.create(self._static_config, gear_idx)
                        success, frame_freq = self._get_frame_freq(gear_frame_qf, STATE_TRANS_QF)
                        if not success:
                            raise RuntimeError("Failed to get trans QF frequency")
                        self._default_timing_freq_qf.append(round(frame_freq, 2))
                    elif state == STATE_TRANS_MF:
                        gear_frame_mf = FrameTimingGear(False, True)
                        gear_frame_mf.create(self._static_config, gear_idx)
                        success, frame_freq = self._get_frame_freq(gear_frame_mf, STATE_TRANS_MF)
                        if not success:
                            raise RuntimeError("Failed to get trans MF frequency")                        
                        self._default_timing_freq_mf.append(round(frame_freq, 2))
                    elif state == STATE_HYBRID_X:
                        gear_frame_hybrid_x = FrameTimingGear(True, False)
                        gear_frame_hybrid_x.create(self._static_config, gear_idx)
                        success, frame_freq = self._get_frame_freq(gear_frame_hybrid_x, STATE_HYBRID_X)
                        if not success:
                            raise RuntimeError("Failed to get Hybrid frequency")                         
                        self._default_timing_freq_hybrid.append(round(frame_freq, 2))
            self._freq_inited = True

            if debug:              
                print(self._max_timing_freq_qf)
                print(self._max_timing_freq_mf)
                print(self._max_timing_freq_hybrid)
                print(self._default_timing_freq_qf)
                print(self._default_timing_freq_mf)
                print(self._default_timing_freq_hybrid)
            return {
                "maxFreqTransQf": self._max_timing_freq_qf, 
                "maxFreqTransMf": self._max_timing_freq_mf,
                "maxFreqHybrid": self._max_timing_freq_hybrid, 
                "defaultFreqTransQf": self._default_timing_freq_qf, 
                "defaultFreqTransMf": self._default_timing_freq_mf,
                "defaultFreqHybrid": self._default_timing_freq_hybrid, 
                }
        except Exception as e:
            print("error: {}".format(e))
            raise e

    def _calculate_noise_gear_results(self, noise_freq_list, noise_usage_list, state_idx):
        list_timing_results = []
        gear_timing_quiet = FrameTimingGear(True, False)
        gear_timing_multi = FrameTimingGear(False, True)
        success_timing_resutls = True
        success_timing_processed = True
        success_timing_gear = True
        num_timing = min(len(noise_freq_list), len(noise_usage_list))
        for gear in range(num_timing):
            timing_result = self._result_create(noise_freq_list[gear], gear)
            is_timing_used = noise_usage_list[gear]
            success_timing_gear = timing_result is not None
            if success_timing_gear:
                gear_timing_quiet.create(self._static_config, gear)
                gear_timing_multi.create(self._static_config, gear)
                timing_result.gear_quiet.is_used = gear_timing_quiet.is_used or is_timing_used
                timing_result.gear_multi.is_used = gear_timing_multi.is_used or is_timing_used
                list_timing_results.append(timing_result)
        if success_timing_gear:    
            success_timing_resutls = True if self._result_calculate_wrapper(list_timing_results, state_idx) else False
            if success_timing_resutls:  
                if not self._result_optimize_wrapper(list_timing_results):
                    success_timing_processed = False
        # Save param_timing
        if not success_timing_resutls:
            raise RuntimeError("Frame timing gear results are invalid.")
        if not success_timing_processed:
            raise RuntimeError("Error occurred in processing timing gear results.")
        if not success_timing_gear:
            raise RuntimeError("Frame timing gear results data is invalid.")        
        return list_timing_results

    def _get_first_freq_gear(self):
        gear_frame = FrameTimingGear(True, False)
        # create the first gear from current sensor settings
        gear_idx = 0
        gear_frame.create(self._static_config, gear_idx)
        # initialize the gear to the smallest stretch-duration
        if gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
          for vars_timing in gear_frame.variables_table:
              vars_timing.rstretch_dur = 0
        return gear_frame

    def _result_create(self, target_freq, gear_idx = 0):
        result_frame = FrameTimingResult()
        result_frame.create(self._static_config, gear_idx)
        self._result_initialize(result_frame, target_freq)
        return result_frame

    def _set_gear_table_variables(self, gear_frame, frame_bandwidth):
        success = True
        if gear_frame is not None: 
            if gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
                for state_idx in range(NUM_STATES):
                    if gear_frame.variables_table[state_idx] is not None:
                        gear_frame.variables_table[state_idx].filter_bandwidth = frame_bandwidth

                        burst_size1, burst_size2 = self._get_frame_burst_size(frame_bandwidth)
                        gear_frame.variables_table[state_idx].burst_size1 = burst_size1
                        gear_frame.variables_table[state_idx].burst_size2 = burst_size2

    def _set_timing_variables(self, static, vars_table, gear_idx):
        namePrefix = vars_table.str_name_prefix
        static['{0}.stretchDur'.format(namePrefix)][gear_idx] = vars_table.stretch_dur
        static['{0}.rstretchDur'.format(namePrefix)][gear_idx] = vars_table.rstretch_dur
        static['{0}.burstSize1'.format(namePrefix)][gear_idx] = vars_table.burst_size1
        static['{0}.burstSize2'.format(namePrefix)][gear_idx] = vars_table.burst_size2
        static['{0}.filtBW'.format(namePrefix)][gear_idx] = vars_table.filter_bandwidth
        static['{0}.disableFreq'.format(namePrefix)][gear_idx] = vars_table.disable_frequency

    def _is_calculation_completed(self):
        return len(self._list_results_noise_trans_qf) == self._num_gears and \
                len(self._list_results_noise_trans_mf) == self._num_gears and \
                len(self._list_results_noise_hybrid_x) == self._num_gears and \
                len(self._list_results_noise_hybrid_y) == self._num_gears

    def _set_static_config(self, static):
        self._tc.sendCommand(56)
        self._tc.getResponse()
        arg = self._tc.decoder.encodeStaticConfig(static)
        self._tc.sendCommand(57, arg)
        self._tc.getResponse()
        self._tc.sendCommand(55)
        self._tc.getResponse()
        time.sleep(0.1)

    # ////////////////////////////////////////
    # --- Result Initialization Flow ----
    # ----------------------------------------
    def _result_initialize(self, result_frame, target_freq):
        if result_frame is not None:
            if result_frame.gear_quiet is not None and result_frame.gear_quiet.variables_table is not None:
                if len(result_frame.gear_quiet.variables_table) == NUM_STATES:
                    for state in range(NUM_STATES):
                        result_frame.gear_quiet.variables_table[state].rstretch_dur = \
                            self._get_frame_stretch_dur(target_freq, result_frame.gear_quiet.variables_table[state], state)
                        result_frame.gear_quiet.variables_table[state].filter_bandwidth = \
                            self._get_frame_filter_bandwidth(target_freq)
                    self._result_initialize_freq(result_frame.gear_quiet, target_freq)

            if result_frame.gear_multi is not None and result_frame.gear_multi.variables_table is not None:
                if len(result_frame.gear_multi.variables_table) == NUM_STATES:
                    for state in range(NUM_STATES):
                        result_frame.gear_multi.variables_table[state].rstretch_dur = \
                            self._get_frame_stretch_dur(target_freq, result_frame.gear_multi.variables_table[state], state)
                        result_frame.gear_multi.variables_table[state].filter_bandwidth = \
                            self._get_frame_filter_bandwidth(target_freq)
                    self._result_initialize_freq(result_frame.gear_multi, target_freq)

    def _result_initialize_freq(self, gear_frame, target_freq):
        success, actual_freq = self._get_frame_freq(gear_frame)
        if success:
            gear_frame.actual_freq = actual_freq
            gear_frame.target_report_rate = self._target_timing_rate
            gear_frame.target_freq = target_freq

    # ////////////////////////////////////////
    # --- Result Optimization Flow ----
    # ----------------------------------------
    def _result_optimize_wrapper(self, list_frame_results):
        success = list_frame_results is not None
        if success and not self._has_constant_noise:
            if not self._result_optimize(list_frame_results, True, False):
                success = False
            if not self._result_optimize(list_frame_results, False, True):
                success = False
        return success

    def _result_optimize(self, list_frame_results, is_quiet_frame, is_multi_frame):
        success = True
        gear_adjusted = False
        gear_budget = (1 / self._target_timing_rate) * 1E6
        gear_extreme = VAL_INVALID
        i = 0
        while success:
            i += 1
            # search through the gears and find the gear with the longest/shortest frame time
            gear_extreme = float('-inf') if self._has_power_noise else float('inf')
            for result in list_frame_results:
                if is_quiet_frame:
                    gear_frame = result.gear_quiet
                elif is_multi_frame:
                    gear_frame = result.gear_multi
                else:
                    gear_frame = None
                frame_time = VAL_INVALID
                success = gear_frame is not None
                if success:
                    success, frame_time = self._get_quiet_frame_time(gear_frame)
                    if success:
                        gear_extreme = max(gear_extreme, frame_time) if self._has_power_noise else min(gear_extreme, frame_time)
                    else:
                        break
                else:
                    break
            # check longest frame-time against report-rate budget
            if gear_extreme >= gear_budget or not success:
                break
            # add the extra increment the filter-bandwidth to all the gears
            if not self._result_add_bw_all(list_frame_results, +1, is_quiet_frame, is_multi_frame):
                success = False
            gear_adjusted = True
            # and update all frame time calculations for all gears in all tables
            if (success and not self._result_update(list_frame_results)):
                success = False
        # move back if we went too far
        if (gear_extreme > gear_budget) and gear_adjusted:
            if success and not self._result_add_bw_all(list_frame_results, -1, is_quiet_frame, is_multi_frame):
                success = False
            if (success and not self._result_update(list_frame_results)):
                success = False             
        return success  

    # ////////////////////////////////////////
    # --- FrameBandwidth Incremental Flow ----
    # ----------------------------------------
    def _result_add_bw_all(self, list_frame_results, frame_increment, is_quiet_frame, is_multi_frame):
        success = list_frame_results is not None
        if success:
            for result in list_frame_results:
                if not self._result_add_bw_wrapper(result, frame_increment, is_quiet_frame, is_multi_frame):
                    success = False
                    break
        return success

    def _result_add_bw_wrapper(self, result_frame, frame_increment, is_quiet_frame, is_multi_frame):
        is_quiet_gear = True if result_frame is not None else False
        is_multi_gear = True if result_frame is not None else False    
        if is_quiet_frame and is_quiet_gear:
            if not self._result_add_bw(result_frame.gear_quiet, frame_increment):
                is_quiet_gear = False
        if is_multi_frame and is_multi_gear:
            if not self._result_add_bw(result_frame.gear_multi, frame_increment):
                is_multi_gear = False
        return (is_quiet_gear and is_multi_gear)

    def _result_add_bw(self, gear_frame, frame_bandwidth):
        success = True
        if gear_frame is not None and gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
            for state in range(NUM_STATES):
                vars_frame = gear_frame.variables_table[state]
                if vars_frame is not None and vars_frame.filter_bandwidth != VAL_INVALID:
                    self._result_set_bw(gear_frame.variables_table[state], vars_frame.filter_bandwidth + frame_bandwidth)
                else:
                    success = False
                    break
        else:
            success = False
        return success

    # ////////////////////////////////////////
    # --- Set Bandwidth/BurstSize Flow ----
    # ----------------------------------------
    def _result_set_bw_all(self, list_frame_results, frame_bandwidth, is_quiet_frame, is_multi_frame):
        success = True if list_frame_results is not None else False
        if success:
            for result in list_frame_results:
                set_successe= self._result_set_bw_wrapper(result, frame_bandwidth, is_quiet_frame, is_multi_frame)
                if not set_successe:
                    success = False
                    break
        return success

    def _result_set_bw_wrapper(self, result_frame, frame_bandwidth, is_quiet_frame, is_multi_frame):
        is_quiet_gear = True if result_frame is not None else False
        is_multi_gear = True if result_frame is not None else False    
        if is_quiet_frame and is_quiet_gear:
            if not self._result_set_bw_all_states(result_frame.gear_quiet, frame_bandwidth):
                is_quiet_gear = False
        if is_multi_frame and is_multi_gear:
            if not self._result_set_bw_all_states(result_frame.gear_multi, frame_bandwidth):
                is_multi_gear = False
        return (is_quiet_gear and is_multi_gear)

    def _result_set_bw_all_states(self, gear_frame, frame_bandwidth):
        success = False
        if gear_frame is not None and gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
            for state in range(NUM_STATES):
                success = self._result_set_bw(gear_frame.variables_table[state], frame_bandwidth)
                if not success:
                    break
        return success

    def _result_set_bw(self, vars_frame, frame_bandwidth):
        if vars_frame is None:
            return False
        if frame_bandwidth <= FILTER_BANDWIDTH_MAX:
            vars_frame.filter_bandwidth = frame_bandwidth
        else: 
            return False
        
        burst_size1, burst_size2 = self._get_frame_burst_size(frame_bandwidth)
        if burst_size1 != VAL_INVALID and burst_size2 != VAL_INVALID:
            vars_frame.burst_size1 = burst_size1
            vars_frame.burst_size2 = burst_size2
        return True

    # ////////////////////////////////////////
    # --- Find Maximum Frequency Flow ----
    # ----------------------------------------                
    def _result_find_wrapper(self, list_frame_results, is_quiet_frame, is_multi_frame):
        success = True if list_frame_results is not None else False
        gear_maximum = VAL_INVALID

        if success:
            for result in list_frame_results:
                frame_value = VAL_INVALID
                result_found, frame_value = self._result_find(result, is_quiet_frame, is_multi_frame)
                if not result_found:
                    success = False
                    break
                gear_maximum = max(gear_maximum, frame_value)
        return success, gear_maximum

    def _result_find(self, result_frame, is_quiet_frame, is_multi_frame):
            maximum_freq = VAL_INVALID
            is_quiet_gear = True if result_frame is not None else False
            is_multi_gear = True if result_frame is not None else False            
            gear_quiet_freq = VAL_INVALID
            gear_multi_freq = VAL_INVALID
            if is_quiet_frame and is_quiet_gear:
                if result_frame.gear_quiet.target_freq is not None:
                    gear_quiet_freq = result_frame.gear_quiet.target_freq
                else:
                    is_quiet_gear = False
            if is_multi_frame and is_multi_gear:
                if result_frame.gear_multi.target_freq is not None:
                    gear_multi_freq = result_frame.gear_multi.target_freq
                else:
                    is_multi_gear = False
            maximum_freq = max(gear_quiet_freq, gear_multi_freq)
            return (is_quiet_gear and is_multi_gear), maximum_freq

    # ////////////////////////////////////////
    # --- Result Calculation Flow ----
    # ----------------------------------------
    def _result_calculate_wrapper(self, list_frame_results, state_idx = STATE_TRANS_QF):
        success = list_frame_results is not None
        if not self._result_calculate(list_frame_results, True, False, state_idx):
            success = False
        if not self._result_calculate(list_frame_results, False, True, state_idx):
            success = False            
        return success

    def _result_calculate(self, list_frame_results, is_quiet_frame, is_multi_frame, state_idx = STATE_TRANS_QF):
        success = False
        find_success, gear_freq = self._result_find_wrapper(list_frame_results, is_quiet_frame, is_multi_frame)
        if find_success:
            frame_bandwidth = self._get_frame_filter_bandwidth(gear_freq)
            if self._result_set_bw_all(list_frame_results, frame_bandwidth, is_quiet_frame, is_multi_frame):
                success = True
        if success and not self._result_update(list_frame_results, state_idx):
            if self._result_set_bw_all(list_frame_results, frame_bandwidth, is_quiet_frame, is_multi_frame):
                success = False
        return success

    def _result_update(self, list_frame_results, state_idx = STATE_TRANS_QF):
        success = list_frame_results is not None
        if success:
            for result in list_frame_results:
                if not self._result_calculate_all_wrapper(result.gear_quiet, list_frame_results, state_idx):
                    success = False
                    break
                if not self._result_calculate_all_wrapper(result.gear_multi, list_frame_results, state_idx):
                    success = False
                    break      
        return success             

    def _result_calculate_all_wrapper(self, gear_frame, list_frame_results, state_idx = STATE_TRANS_QF):
        success = False
        if gear_frame is not None and gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
            success = True
            self._result_clear(gear_frame)
            if not self._result_calculate_all(gear_frame, gear_frame.is_freq_quiet, gear_frame.is_freq_multi, list_frame_results, state_idx):
                success = False
            # Todo: Check

            gear_frame.is_valid = success and self._result_valid(gear_frame)
        return success

    def _result_calculate_all(self, gear_frame, is_quiet_frame, is_multi_frame, list_frame_results, state_idx = STATE_TRANS_QF):
        success, frame_value = self._get_frame_freq(gear_frame, state_idx)
        if success: gear_frame.actual_freq = frame_value
        success, frame_value = self._get_frame_time_wrapper(is_quiet_frame, is_multi_frame, gear_frame, list_frame_results)
        if success: gear_frame.frame_time = frame_value
        success, frame_value = self._get_frame_rate_w_multi_burst(is_quiet_frame, is_multi_frame, gear_frame, list_frame_results)
        if success: gear_frame.frame_rate = frame_value
        success, frame_value = self._get_actual_report_rate(gear_frame)
        if success: gear_frame.actual_report_rate = frame_value
        success, frame_value = self._get_frame_report_rate_wrapper(gear_frame, gear_frame.target_report_rate)
        if success: gear_frame.frame_report_rate = frame_value
        success, frame_value = self._get_frame_period_wrapper(gear_frame)
        if success: gear_frame.frame_period = frame_value
        success, frame_value = self._get_frame_idle_wrapper(gear_frame)
        if success: gear_frame.frame_idle = frame_value
        success, frame_value = self._get_frame_acquisition_wrapper(gear_frame)
        if success: gear_frame.frame_acquisition = frame_value
        return success

    def _result_clear(self, gear_frame):
        if gear_frame is not None:
            gear_frame.actual_freq = None
            gear_frame.actual_report_rate = None
            gear_frame.frame_report_rate = None
            gear_frame.frame_time = None
            gear_frame.frame_rate = None
            gear_frame.frame_period = None
            gear_frame.frame_idle = None
            gear_frame.frame_acquisition = None

    def _result_valid(self, gear_frame):
        # make sure have not blown the frame-rate budget
        valid = gear_frame is not None
        if valid:
            min_bandwidth = self._get_frame_filter_bandwidth(gear_frame.actual_freq)
            for state in range(NUM_STATES):
                valid = True if gear_frame.variables_table[state].filter_bandwidth >= min_bandwidth else False
                if not valid:
                    break
        return valid

    # ////////////////////////////////////////
    # --- Get Frame Timing Variables ----
    # ----------------------------------------
    # stretch dur
    def _get_frame_stretch_dur(self, target_freq, vars_frame, state_idx):
        frame_dur = VAL_INVALID
        if state_idx == STATE_TRANS_QF:
            frame_dur = self._get_trans_stretch_dur(vars_frame, target_freq, False)
        elif state_idx == STATE_TRANS_MF:
            frame_dur = self._get_trans_stretch_dur(vars_frame, target_freq, True)
        elif state_idx == STATE_HYBRID_X or state_idx == STATE_HYBRID_Y:
            frame_dur = self._get_hybrid_stretch_dur(vars_frame, target_freq)
        return frame_dur       

    def _get_trans_stretch_dur(self, vars_frame, frame_freq, is_trans_mf = False):
        frame_dur = VAL_INVALID
        if self._param_frame is not None:
            frame_dur = (1E3 * self._param_frame.average_clock) / (2 * frame_freq)
            if not is_trans_mf:
                frame_dur -= vars_frame.stretch_dur + self._param_frame.image_int_dur + self._param_frame.image_reset_dur
            else:
                frame_dur -= vars_frame.stretch_dur + self._param_frame.image_int_dur_mf + self._param_frame.image_reset_dur
            frame_dur -= self._sample_duration + self._other_overhead
        return max(round(frame_dur), 0)
    
    def _get_hybrid_stretch_dur(self, vars_frame, frame_freq):
        frame_dur = VAL_INVALID
        if self._param_frame is not None:
            frame_dur = (1E3 * self._param_frame.average_clock) / (2 * frame_freq)
            frame_dur -= vars_frame.stretch_dur + self._param_frame.hybrid_int_dur + self._param_frame.hybrid_reset_dur
            frame_dur -= self._sample_duration + self._other_overhead
        return max(round(frame_dur), 0)

    # filter bandwidth
    def _get_frame_filter_bandwidth(self, frame_freq):
        if frame_freq is not None and frame_freq != VAL_INVALID:
            if frame_freq < 254.386:
                return 0
            elif frame_freq < 258.929:
                return 3
            elif frame_freq < 273.585:
                return 2
            elif frame_freq < 345.238:
                return 4
            elif frame_freq < 483.333:
                return 5
            else:
                return 6        
        return VAL_INVALID

    # burst size
    def _get_frame_burst_size(self, frame_bandwidth):
        # burstSize1array[] = {11 12 13 14 17 19 21 24 28 34 40 44 54 65 77 110}
        # burstSize2array[] = { 8  8  9  9 11 12 13 16 20 22 25 29 37 37 42 56
        if frame_bandwidth == 0:
            return 11, 8
        elif frame_bandwidth == 1:
            return 12, 8
        elif frame_bandwidth == 2:
            return 13, 9
        elif frame_bandwidth == 3:
            return 14, 9
        elif frame_bandwidth == 4:
            return 17, 11
        elif frame_bandwidth == 5:
            return 19, 12
        elif frame_bandwidth == 6:
            return 21, 13
        elif frame_bandwidth == 7:
            return 24, 16
        elif frame_bandwidth == 8:
            return 28, 20
        elif frame_bandwidth == 9:
            return 34, 22
        elif frame_bandwidth == 10:
            return 40, 25
        elif frame_bandwidth == 11:
            return 44, 29
        elif frame_bandwidth == 12:
            return 54, 37
        elif frame_bandwidth == 13:
            return 65, 37
        elif frame_bandwidth == 14:
            return 77, 42
        elif frame_bandwidth == 15:
            return 110, 56
        else:
            return (VAL_INVALID, VAL_INVALID)

    # ////////////////////////////////////////
    # --- Get Frame Timing Gear Parameters ----
    # ----------------------------------------
    # frame frequency  
    def _get_frame_freq(self, gear_frame, frame_state = STATE_TRANS_QF):
        if gear_frame is not None:
            if gear_frame.variables_table is not None and frame_state < NUM_STATES:
                freq_frame = VAL_INVALID
                if frame_state == STATE_TRANS_QF:
                    freq_frame = self._get_trans_frame_freq(gear_frame.variables_table[frame_state], False)
                elif frame_state == STATE_TRANS_MF:
                    freq_frame = self._get_trans_frame_freq(gear_frame.variables_table[frame_state], True)
                elif frame_state == STATE_HYBRID_X or frame_state == STATE_HYBRID_Y:
                    freq_frame = self._get_hybrid_frame_freq(gear_frame.variables_table[frame_state])
                return (True, freq_frame)         
        return (False, None)

    def _get_trans_frame_freq(self, vars_frame, is_trans_mf = False):
        half_cycle = VAL_INVALID        
        if self._param_frame is not None:
            half_cycle = vars_frame.stretch_dur + vars_frame.rstretch_dur
            if not is_trans_mf:
                half_cycle += self._param_frame.image_int_dur + self._param_frame.image_reset_dur
            else:
                half_cycle += self._param_frame.image_int_dur_mf + self._param_frame.image_reset_dur
            half_cycle += self._sample_duration + self._other_overhead
            half_cycle /= self._param_frame.average_clock   
            frame_freq = 1E3 / (2 * half_cycle) 
        return frame_freq
    
    def _get_hybrid_frame_freq(self, vars_frame):
        half_cycle = VAL_INVALID
        if self._param_frame is not None:
            half_cycle = vars_frame.stretch_dur + vars_frame.rstretch_dur
            half_cycle += self._param_frame.hybrid_int_dur + self._param_frame.hybrid_reset_dur
            half_cycle += self._sample_duration + self._other_overhead
            half_cycle /= self._param_frame.average_clock
            frame_freq = 1E3 / (2 * half_cycle)
        return frame_freq

    # frame time
    def _get_frame_time_wrapper(self, is_quiet_frame, is_multi_frame, gear_frame, list_results_frame):
        if gear_frame is not None:
            if is_quiet_frame and not is_multi_frame:
                return self._get_frame_time(False, gear_frame, list_results_frame, True, False)
            if is_multi_frame and not is_quiet_frame:
                return self._get_frame_time(False, gear_frame, list_results_frame, False, True)
        return (False, None)    

    def _get_frame_time(self, is_multi_burst, gear_frame, list_results_frame, is_quiet_frame, is_multi_frame):
        if is_quiet_frame and not is_multi_frame:
            return self._get_quiet_frame_time_wrapper(gear_frame)
        if is_multi_frame and not is_quiet_frame:
            return self._get_multi_frame_time_wrapper(is_multi_burst, gear_frame, list_results_frame)
        return (False, None)    

    def _get_quiet_frame_time_wrapper(self, gear_frame):
        if gear_frame is None:
            return (False, None) 
        if gear_frame.is_freq_quiet and gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
            success, frame_time = self._get_quiet_frame_time(gear_frame)
            if success:
                return (True, frame_time)
        return (False, None) 

    def _get_quiet_frame_time(self, gear_frame):
        is_table_length_correct = False
        if gear_frame is not None and gear_frame.variables_table is not None:
            is_table_length_correct = len(gear_frame.variables_table) == NUM_STATES
        
        if is_table_length_correct:
            vars_frame_trans = gear_frame.variables_table[STATE_TRANS_QF]
            vars_frame_hybrid_x = gear_frame.variables_table[STATE_HYBRID_X]
            vars_frame_hybrid_y = gear_frame.variables_table[STATE_HYBRID_Y]

            if vars_frame_trans is not None and vars_frame_hybrid_x is not None and vars_frame_hybrid_y is not None:
                # for QF NOISE:
                half_cycle_noise_qf = (vars_frame_trans.stretch_dur + vars_frame_trans.rstretch_dur + self._param_frame.int_dur_noise_qf \
                                    + self._param_frame.reset_dur_noise + self._sample_duration + self._other_overhead) / FTAC
                burst_first_noise_qf = (vars_frame_trans.burst_size1 + 1) * (2 * half_cycle_noise_qf)
                burst_add_noise_qf = (vars_frame_trans.burst_size2) * (2 * burst_first_noise_qf)
                frame_time_noise_qf = ((burst_first_noise_qf) + ((self._param_frame.image_bursts_per_cluster_qf - 1) * burst_add_noise_qf)) \
                                    * self._param_frame.subframe_num_clusters_noise

                #Assuming a gear is chosen:
                # For QF TRANS:
                half_cycle_trans_qf = (vars_frame_trans.stretch_dur + vars_frame_trans.rstretch_dur + self._param_frame.int_dur_trans_qf \
                                    + self._param_frame.reset_dur_trans + self._sample_duration + self._other_overhead) / FTAC
                burst_first_trans_qf = (vars_frame_trans.burst_size1 + 1) * (2 * half_cycle_trans_qf)
                burst_add_trans_qf = (vars_frame_trans.burst_size2) * (2 * burst_first_trans_qf)
                frame_time_trans_qf = ((burst_first_trans_qf + HARD_RESET_DUR) + ((self._param_frame.image_bursts_per_cluster_qf - 1) * burst_add_trans_qf)) \
                                    * self._param_frame.subframe_num_clusters_trans

                # for QF AbsRx (ABSX):
                stall_time_absrx_qf = (2*(vars_frame_hybrid_x.rstretch_dur-9)+ 2*(self._param_frame.reset_dur_absrx-1)+ 2*vars_frame_hybrid_x.stretch_dur + self._param_frame.int_dur_absrx_qf-26)/FTAC
                half_cycle_abs_rx_qf = (vars_frame_hybrid_x.stretch_dur + vars_frame_hybrid_x.rstretch_dur + self._param_frame.int_dur_absrx_qf + self._param_frame.reset_dur_absrx\
                                    + self._sample_duration + self._other_overhead)/FTAC
                burst_first_abs_rx_qf = (vars_frame_hybrid_x.burst_size1 + 1)*(2*half_cycle_abs_rx_qf)
                burst_add_abs_rx_qf = (vars_frame_hybrid_x.burst_size2)*(2*burst_first_abs_rx_qf)
                frame_time_abs_rx_qf = ((burst_first_abs_rx_qf + HARD_RESET_DUR) + ((self._param_frame.hybrid_x_bursts_per_cluster_qf - 1)*burst_add_abs_rx_qf)) \
                                    * self._param_frame.subframe_num_clusters_absrx + stall_time_absrx_qf

                # for QF AbsTx (ABSY):
                stall_time_abstx_qf = ((vars_frame_hybrid_y.rstretch_dur-9)+ (self._param_frame.reset_dur_abstx-1)+ vars_frame_hybrid_y.stretch_dur + self._param_frame.int_dur_abstx_qf-26)/FTAC
                half_cycle_abs_tx_qf = ((vars_frame_hybrid_y.stretch_dur + vars_frame_hybrid_y.rstretch_dur + self._param_frame.int_dur_abstx_qf + self._param_frame.reset_dur_abstx \
                                    + self._sample_duration + self._other_overhead))/FTAC
                burst_first_abs_tx_qf = (vars_frame_hybrid_y.burst_size1 + 1)*(2*half_cycle_abs_tx_qf)
                burst_add_abs_tx_qf = (vars_frame_hybrid_y.burst_size2)*(2*burst_first_abs_tx_qf)
                frame_time_abs_tx_qf = ((burst_first_abs_tx_qf + HARD_RESET_DUR) + ((self._param_frame.hybrid_y_bursts_per_cluster_qf - 1)*burst_add_abs_tx_qf)) \
                                    * self._param_frame.subframe_num_clusters_abstx + stall_time_abstx_qf

                # ABSNB (Abs Noise) only happens in QF
                half_cycle_abs_noise_qf = (vars_frame_hybrid_y.stretch_dur + vars_frame_hybrid_y.rstretch_dur + self._param_frame.int_dur_absnb_qf + self._param_frame.reset_dur_absnb \
                                        + self._sample_duration + self._other_overhead)/FTAC
                burst_first_abs_noise_qf = (vars_frame_hybrid_x.burst_size1 + 1)*(2*half_cycle_abs_noise_qf)
                burst_add_abs_noise_qf = (vars_frame_hybrid_x.burst_size2)*(2*burst_first_abs_noise_qf)
                frame_time_abs_noise_qf = ((burst_first_abs_noise_qf) + ((self._param_frame.image_bursts_per_cluster_qf - 1)*burst_add_abs_noise_qf))*self._param_frame.subframe_num_clusters_absnb

                end_of_frame_stall_time_qf = 493.4E-6 - 12.05E-6  # base + avg effect of change in I/RS within 50 tac cycles of baseline 26/9
                full_frame_qf = (frame_time_noise_qf + frame_time_trans_qf + frame_time_abs_rx_qf + frame_time_abs_tx_qf + frame_time_abs_noise_qf+ end_of_frame_stall_time_qf)*1E6
                return (True, full_frame_qf)
        return (False, None)

    def _get_multi_frame_time_wrapper(self, is_multi_burst, gear_frame, list_results_frames):
        if gear_frame is None:
            return (False, None) 
        if gear_frame.is_freq_multi and gear_frame.variables_table is not None and len(gear_frame.variables_table) == NUM_STATES:
            list_gears_mf = []
            list_gears_qf = []
            for result in list_results_frames:
                if result.gear_multi is not None and result.gear_multi.variables_table is not None and len(result.gear_multi.variables_table) == NUM_STATES:
                    list_gears_mf.append(result.gear_multi)
                if result.gear_quiet is not None and result.gear_quiet.variables_table is not None and len(result.gear_quiet.variables_table) == NUM_STATES:
                    list_gears_qf.append(result.gear_quiet)
            success, frame_time = self._get_multi_frame_time(is_multi_burst, gear_frame, list_gears_mf, list_gears_qf)
            if success:
                return (True, frame_time)
        return (False, None) 

    def _get_multi_frame_time(self, is_frame_multi_burst, gear_frame, list_gears_mf, list_gears_qf):
        is_table_length_correct = False
        if gear_frame is not None and gear_frame.variables_table is not None:
            is_table_length_correct = len(gear_frame.variables_table) == NUM_STATES

        if is_table_length_correct and list_gears_mf is not None and list_gears_qf is not None:
            gear_used_mf = []
            gear_used_qf = []
            for idx, gear in enumerate(list_gears_mf):
                if (list_gears_mf[idx].is_freq_multi and list_gears_mf[idx].is_used):
                    gear_used_mf.append(idx)
            for idx, gear in enumerate(list_gears_qf):
                if (list_gears_qf[idx].is_freq_quiet and list_gears_qf[idx].is_used):
                    gear_used_qf.append(idx)

            multi_burst_multiplier = 2 if is_frame_multi_burst == True else 1
            vars_frame_trans_qf = gear_frame.variables_table[STATE_TRANS_QF]
            vars_frame_trans_mf = gear_frame.variables_table[STATE_TRANS_MF]
            vars_frame_hybrid_x = gear_frame.variables_table[STATE_HYBRID_X]
            vars_frame_hybrid_y = gear_frame.variables_table[STATE_HYBRID_Y]

            half_cycle_noise_mf = [None for i in range(len(gear_used_mf))]
            burst_first_noise_mf = [None for i in range(len(gear_used_mf))]
            burst_add_noise_mf = [None for i in range(len(gear_used_mf))]
            per_gear_frame_time_noise_mf = [None for i in range(len(gear_used_mf))]

            # for MF NOISE loop over enabled gears:
            for i in range(len(gear_used_mf)):
                used_gear_idx = gear_used_mf[i]
                vars_gear_trans_mf = list_gears_mf[used_gear_idx].variables_table[STATE_TRANS_MF]    

                half_cycle_noise_mf[i] = (vars_gear_trans_mf.stretch_dur + vars_gear_trans_mf.rstretch_dur + self._param_frame.int_dur_noise_mf \
                                    + self._param_frame.reset_dur_noise + self._sample_duration + self._other_overhead) / FTAC
                burst_first_noise_mf[i] = (vars_gear_trans_mf.burst_size1 + 1) * (2 * half_cycle_noise_mf[i])
                burst_add_noise_mf[i] = (vars_gear_trans_mf.burst_size2) * (2 * burst_first_noise_mf[i])
                per_gear_frame_time_noise_mf[i] = ((burst_first_noise_mf[i]) + ((self._param_frame.image_bursts_per_cluster_mf - 1) * burst_add_noise_mf[i]))
            frame_time_noise_mf = sum(per_gear_frame_time_noise_mf)

            #PMFNB (PowerIM in MF Noise Burst) runs noise bursts in MF only at the first available TRANS frequency
            frame_time_pmfnb_mf =  0
            half_cycle_pmfnb_qf = (vars_frame_trans_qf.stretch_dur + vars_frame_trans_qf.rstretch_dur + self._param_frame.int_dur_pmfnb_qf \
                                + self._param_frame.reset_dur_pmfnb + self._sample_duration + self._other_overhead) / FTAC
            burst_first_pmfnb_qf = (vars_frame_trans_qf.burst_size1 + 1) * (2 * half_cycle_pmfnb_qf)
            burst_add_pmfnb_qf = (vars_frame_trans_qf.burst_size2) * (2 * half_cycle_pmfnb_qf)
            frame_time_pmfnb_mf = (burst_first_pmfnb_qf + ((self._param_frame.image_bursts_per_cluster_qf - 1) * burst_add_pmfnb_qf)) \
                                * self._param_frame.subframe_num_clusters_pmfnb

            # For MF TRANS:
            half_cycle_trans_Mf = (vars_frame_trans_mf.stretch_dur + vars_frame_trans_mf.rstretch_dur + self._param_frame.int_dur_trans_mf \
                                + self._param_frame.reset_dur_trans + self._sample_duration + self._other_overhead) / FTAC
            burst_first_trans_mf = (vars_frame_trans_mf.burst_size1 + 1) * (2 * half_cycle_trans_Mf)
            burst_add_trans_mf = (vars_frame_trans_mf.burst_size2) * (2 * burst_first_trans_mf)
            frame_time_trans_mf = ((burst_first_trans_mf + HARD_RESET_DUR) + ((self._param_frame.image_bursts_per_cluster_mf - 1) * burst_add_trans_mf)) \
                                * self._param_frame.subframe_num_clusters_trans * multi_burst_multiplier

            frame_time_trans_mf_no_mb = ((burst_first_trans_mf + HARD_RESET_DUR) + ((self._param_frame.image_bursts_per_cluster_mf - 1) * burst_add_trans_mf)) \
                                * self._param_frame.subframe_num_clusters_trans
           
            # for MF AbsRx (ABSX):
            # In MF the frame program is looping over settings of each enabled ABS frequency. Thus if G is an index into an ABS gears table for a corresponding setting:            stall_time_abstx_qf = ((vars_frame_hybrid_y.rstretch_dur-9)+ (param_frame.reset_dur_abstx-1)+ vars_frame_hybrid_y.stretch_dur + param_frame.int_dur_abstx_qf-26)/FTAC
            stall_time_absrx_mf = (2*(vars_frame_hybrid_x.rstretch_dur-9)+ 2*(self._param_frame.reset_dur_absrx-1)+ \
                                2*vars_frame_hybrid_x.stretch_dur + self._param_frame.int_dur_absrx_mf-26)/FTAC

            half_cycle_absrx_mf = [None for i in range(len(gear_used_mf))]
            burst_first_absrx_mf = [None for i in range(len(gear_used_mf))]
            burst_add_absrx_mf = [None for i in range(len(gear_used_mf))]
            per_gear_frame_time_absrx_mf = [None for i in range(len(gear_used_mf))]
            for i in range(len(gear_used_mf)):
                used_gear_idx = gear_used_mf[i]
                vars_gear_hybrid_x = list_gears_mf[used_gear_idx].variables_table[STATE_HYBRID_X]

                half_cycle_absrx_mf[i] = ((vars_gear_hybrid_x.stretch_dur + vars_gear_hybrid_x.rstretch_dur + self._param_frame.int_dur_absrx_mf + self._param_frame.reset_dur_absrx \
                                    + self._sample_duration + self._other_overhead))/FTAC
                burst_first_absrx_mf[i] = (vars_gear_hybrid_x.burst_size1 + 1)*(2*half_cycle_absrx_mf[i])
                burst_add_absrx_mf[i] = (vars_gear_hybrid_x.burst_size2)*(2*half_cycle_absrx_mf[i])
                per_gear_frame_time_absrx_mf[i] = ((burst_first_absrx_mf[i] + HARD_RESET_DUR) + ((self._param_frame.hybrid_x_bursts_per_cluster_mf - 1)*burst_add_absrx_mf[i])) \
                                    * self._param_frame.subframe_num_clusters_absrx
                                
            frame_time_absrx_mf = sum(per_gear_frame_time_absrx_mf) + stall_time_absrx_mf
  
            # for MF AbsTx (ABSY):
            # In MF the frame program is looping over settings of each enabled ABS frequency. Thus if G is an index into an ABS gear table for a corresponding setting:            half_cycle_abs_noise_qf = (vars_frame_hybrid_y.stretch_dur + vars_frame_hybrid_y.rstretch_dur + param_frame.int_dur_absnb_qf + param_frame.reset_dur_absnb \

            stall_time_abstx_mf = ((vars_frame_hybrid_y.rstretch_dur-9)+ (self._param_frame.reset_dur_abstx-1)+ \
                                vars_frame_hybrid_y.stretch_dur + self._param_frame.int_dur_abstx_mf-26)/FTAC
            half_cycle_abstx_mf = [None for i in range(len(gear_used_mf))]
            burst_first_abstx_mf = [None for i in range(len(gear_used_mf))]
            burst_add_abstx_mf = [None for i in range(len(gear_used_mf))]
            per_gear_frame_time_abstx_mf = [None for i in range(len(gear_used_mf))]
            for i in range(len(gear_used_mf)):
                used_gear_idx = gear_used_mf[i]
                vars_gear_hybrid_y = list_gears_mf[used_gear_idx].variables_table[STATE_HYBRID_Y]

                half_cycle_abstx_mf[i] = ((vars_gear_hybrid_y.stretch_dur + vars_gear_hybrid_y.rstretch_dur + self._param_frame.int_dur_abstx_mf + self._param_frame.reset_dur_abstx \
                                    + self._sample_duration + self._other_overhead))/FTAC
                burst_first_abstx_mf[i] = (vars_gear_hybrid_y.burst_size1 + 1)*(2*half_cycle_abstx_mf[i])
                burst_add_abstx_mf[i] = (vars_gear_hybrid_y.burst_size2)*(2*half_cycle_abstx_mf[i])
                per_gear_frame_time_abstx_mf[i] = ((burst_first_abstx_mf[i] + HARD_RESET_DUR) + ((self._param_frame.hybrid_y_bursts_per_cluster_mf - 1)*burst_add_abstx_mf[i])) \
                                    * self._param_frame.subframe_num_clusters_abstx
            frame_time_abstx_mf = sum(per_gear_frame_time_abstx_mf) + stall_time_abstx_mf   
            abstx_factor_mf = 2.2 * (self._param_frame.int_dur_abstx_mf - 26)
            end_of_frame_stall_Time_mf = 506.3E-6 + (5.2E-6) + abstx_factor_mf*1E-6 # base + avg effect of change in I/RS parameters
            
            full_frame_mf_no_mb = (frame_time_noise_mf+ frame_time_pmfnb_mf+ frame_time_trans_mf_no_mb+ frame_time_absrx_mf + frame_time_abstx_mf+end_of_frame_stall_Time_mf)*1E6
            full_frame_mf_mb = (frame_time_noise_mf+ frame_time_pmfnb_mf+ frame_time_trans_mf+ frame_time_absrx_mf + frame_time_abstx_mf+end_of_frame_stall_Time_mf)*1E6 
            return (True, full_frame_mf_mb if is_frame_multi_burst else full_frame_mf_no_mb)
        return (False, None)    

    # frame rate
    def _get_frame_rate_w_multi_burst(self, is_quiet_frame, is_multi_frame, gear_frame, list_results_frame):
        if gear_frame is not None:
            if is_quiet_frame and not is_multi_frame:
                return (True, None) 
            if is_multi_frame and not is_quiet_frame:
                success_frame_rate, frame_rate = self._get_frame_rate_wrapper(True, gear_frame, list_results_frame, gear_frame.is_freq_quiet, gear_frame.is_freq_multi)
                if success_frame_rate:
                    success_report_rate, report_rate = self._get_frame_report_rate_wrapper(gear_frame, gear_frame.target_report_rate)
                    if success_report_rate:
                        return (True, min(frame_rate, report_rate))
        return (False, None)    

    def _get_frame_rate_wrapper(self, is_multi_butst, gear_frame, list_results_frames, is_quiet_frame, is_multi_frame):
        success = False
        frame_time = VAL_INVALID
        frame_rate = VAL_INVALID
        if not is_quiet_frame and not is_multi_frame:
            success, frame_time = self._get_quiet_frame_time(gear_frame)
            if not success:
                return (False, frame_rate)
        if not is_quiet_frame and is_multi_frame:
            success, frame_time = self._get_multi_frame_time_wrapper(is_multi_butst, gear_frame, list_results_frames)
            if not success:
                return (False, frame_rate)
        return self._get_frame_rate(frame_time)

    def _get_frame_rate(self, frame_time):
        if frame_time is not None:
            frame_rate = 1E6 / frame_time
            return (True, frame_rate)
        else: 
            return (False, frame_rate)

    # actual report rate
    def _get_actual_report_rate(self, gear_frame):
        if gear_frame is not None:
            return (self._get_frame_rate(gear_frame.frame_time))
        return (False, None)

    # frame report rate
    def _get_frame_report_rate_wrapper(self, gear_frame, frame_target_rate):
        success_from_actual, actual_rate = self._get_report_rate_from_frame_time(gear_frame)
        success_from_target, target_rate = self._get_report_rate_from_target_rate(frame_target_rate)
        if success_from_actual and success_from_target:
            return (True, min(actual_rate, target_rate))
        return (False, None)

    # frame report rate based on actual frame time
    def _get_report_rate_from_frame_time(self, gear_frame):
        if gear_frame is not None:
            return (self._get_frame_rate(gear_frame.frame_time))
        return (False, None)

    # frame report rate based on target rate
    def _get_report_rate_from_target_rate(self, frame_report_rate):
        if frame_report_rate is not None:
            frame_active = math.floor((1/frame_report_rate)*100000)
            frame_report_rate = 100000/frame_active
            return (True, frame_report_rate)
        return (False, None)

    # frame period
    def _get_frame_period_wrapper(self, gear_frame):
        if gear_frame is not None and gear_frame.frame_report_rate is not None:
            frame_period = self._get_frame_period(gear_frame.frame_report_rate)
            if frame_period is not None:
                return (True, frame_period)
        return (False, None)

    def _get_frame_period(self, frame_report_rate):
        return (1E6/frame_report_rate) if frame_report_rate != 0 else None
    
    # idle time
    def _get_frame_idle_wrapper(self, gear_frame):
        if gear_frame is not None and gear_frame.frame_time is not None and gear_frame.frame_report_rate is not None:
            frame_idle = self._get_frame_idle(gear_frame.frame_time, gear_frame.frame_report_rate)
            if frame_idle is not None:
                return (True, frame_idle)
        return (False, None)

    def _get_frame_idle(self, frame_time, frame_report_rate):
        return (1E6/frame_report_rate - frame_time) if frame_report_rate != 0 else (False, None)
    
    # frame acquisition percent
    def _get_frame_acquisition_wrapper(self, gear_frame):
        if gear_frame is not None and gear_frame.frame_time is not None and gear_frame.frame_report_rate is not None:
            frame_acquisition = self._get_frame_acquisition(gear_frame.frame_time, gear_frame.frame_report_rate)
            if frame_acquisition is not None:
                return (True, frame_acquisition)
        return (False, None)

    def _get_frame_acquisition(self, frame_time, frame_report_rate):
        return ((frame_time/1E6) * frame_report_rate) * 100

    # frame active period
    def _get_frame_active_period(self, list_results_frames):
        if list_results_frames is not None:
            frame_rate = VAL_INVALID
            frame_count = 0
            for result in list_results_frames:
                if result is not None and result.gear_quiet is not None and result.gear_multi is not None:
                    if result.gear_quiet.frame_report_rate is not None and result.gear_multi.frame_report_rate is not None:
                        frame_rate = max(frame_rate, result.gear_quiet.frame_report_rate)
                        frame_rate = max(frame_rate, result.gear_multi.frame_report_rate)
                        frame_count += 1
            if frame_count == len(list_results_frames):
                # return (success, frame report rate, frame active)
                return (True, frame_rate, math.ceil((1/frame_rate)*100000))
        return (False, None, None)

    # ////////////////////////////////////////
    # --- Gear Usage Update Utilities ----
    # ----------------------------------------
    def _enable_results(self, list_frame_results, is_gear_quiet, is_gear_multi, state_idx):
        success = True
        for result in list_frame_results:
            if not self._enable_result(result, is_gear_quiet, is_gear_multi):
                success = False
        self._update_gears(list_frame_results, state_idx)
        if not success:
            return False
        return True

    def _update_results(self, list_frame_results, state_idx):
        success = True
        #GetResults
        state_idx = 0
        if not self._result_update(list_frame_results, state_idx):
            success= False
        self._update_gears(list_frame_results, state_idx)
        if not success:
            return False
        return True

    def _enable_result(self, gear_result, is_gear_quiet, is_gear_multi):
        is_valid_gear = False
        if gear_result is not None:            
            if gear_result.validate(is_gear_quiet, is_gear_multi):
                is_valid_gear = True
        #self._update_usage(gear_result)
        return is_valid_gear

    def _update_gears(self, list_frame_results, state_idx):
        for result in list_frame_results:
            self._update_result(result)
        success_active_period, gear_report_rate, gear_active_period = self._get_frame_active_period(list_frame_results)

    def _update_result(self, gear_result):
        self._update_value(gear_result)
        #self._update_usage(gear_result)

    def _update_value(self, gear_result):
        if gear_result is not None and gear_result.gear_quiet is not None and gear_result.gear_quiet.is_freq_quiet:
            if gear_result.gear_quiet.is_valid:
                gear_result.gear_quiet.gear_value = gear_result.gear_quiet.frame_report_rate
            else:
                gear_result.gear_quiet.gear_value = VAL_INVALID
        if gear_result is not None and gear_result.gear_multi is not None and gear_result.gear_multi.is_freq_multi:
            if gear_result.gear_multi.is_valid:
                gear_result.gear_multi.gear_value = gear_result.gear_multi.frame_report_rate
            else:
                gear_result.gear_multi.gear_value = VAL_INVALID

    def _update_usage(self, gear_result):
        is_used = False        
        if gear_result is not None:
            is_quiet_used = gear_result.gear_quiet.is_used
            is_multi_used = gear_result.gear_multi.is_used
            is_used = is_quiet_used or is_multi_used

    # ////////////////////////////////////////
    # --- Web API Response Utilities ----
    # ----------------------------------------
    def _generate_gear_result_json(self, list_gear_results):
        gear_result_json = [0 for i in range(len(list_gear_results))]
        for idx, result in enumerate(list_gear_results):
            gear_result_json[idx] = {}
            for result_type in ['gear_quiet','gear_multi']:
                if result_type == 'gear_quiet':
                    result_gear = result.gear_quiet
                else:
                    result_gear = result.gear_multi
                gear_result_json[idx][result_type] = {}
                gear_result_json[idx][result_type]['is_freq_quiet'] = result_gear.is_freq_quiet
                gear_result_json[idx][result_type]['is_freq_multi'] = result_gear.is_freq_multi
                gear_result_json[idx][result_type]['is_used'] = result_gear.is_used
                gear_result_json[idx][result_type]['is_valid'] = result_gear.is_valid
                gear_result_json[idx][result_type]['target_freq'] = self._round(result_gear.target_freq)
                gear_result_json[idx][result_type]['actual_freq'] = self._round(result_gear.actual_freq)
                gear_result_json[idx][result_type]['target_report_rate'] = self._round(result_gear.target_report_rate)
                gear_result_json[idx][result_type]['actual_report_rate'] = self._round(result_gear.actual_report_rate)
                gear_result_json[idx][result_type]['frame_report_rate'] = self._round(result_gear.frame_report_rate)
                gear_result_json[idx][result_type]['frame_time'] = self._round(result_gear.frame_time)
                gear_result_json[idx][result_type]['frame_rate'] = self._round(result_gear.frame_rate)
                gear_result_json[idx][result_type]['frame_period'] = self._round(result_gear.frame_period)
                gear_result_json[idx][result_type]['frame_idle'] = self._round(result_gear.frame_idle)
                gear_result_json[idx][result_type]['frame_acquisition'] = self._round(result_gear.frame_acquisition)
                gear_result_json[idx][result_type]['variables_table'] ={}
                gear_result_json[idx][result_type]['param_data'] ={}
                for state in range(NUM_STATES):
                    gear_result_json[idx][result_type]['variables_table'][state] = result_gear.variables_table[state].__dict__
                    gear_result_json[idx][result_type]['param_data'][state] = result_gear.param_data[state].__dict__
        return gear_result_json

    def _round(self, value):
        return round(value,2) if value is not None else None

class FrameTimingParameters(object):
    def __init__(self, **kwargs):
        self.tx_count = kwargs['txCount'] if 'txCount' in kwargs else None
        self.rx_count = kwargs['rxCount'] if 'rxCount' in kwargs else None
        self.has_profiles = kwargs['hasProfiles'] if 'hasProfiles' in kwargs else None
        self.image_int_dur = kwargs['integDur'][SFTYPE_TRANS] if 'integDur' in kwargs else None
        self.image_int_dur_mf = kwargs['integDurMF'][SFTYPE_TRANS] if 'integDurMF' in kwargs else None
        self.hybrid_int_dur = kwargs['integDur'][SFTYPE_ABSTX] if 'integDur' in kwargs else None
        self.image_reset_dur = kwargs['resetDur'][SFTYPE_TRANS] if 'resetDur' in kwargs else None
        self.hybrid_reset_dur = kwargs['resetDur'][SFTYPE_ABSTX] if 'resetDur' in kwargs else None        
        self.int_dur_noise_qf = kwargs['integDur'][SFTYPE_NOISE] if 'integDur' in kwargs else None
        self.int_dur_trans_qf = kwargs['integDur'][SFTYPE_TRANS] if 'integDur' in kwargs else None
        self.int_dur_absrx_qf = kwargs['integDur'][SFTYPE_ABSRX] if 'integDur' in kwargs else None
        self.int_dur_abstx_qf = kwargs['integDur'][SFTYPE_ABSTX] if 'integDur' in kwargs else None
        self.int_dur_absnb_qf = kwargs['integDur'][SFTYPE_ABSNB] if 'integDur' in kwargs else None
        self.int_dur_pmfnb_qf = kwargs['integDur'][SFTYPE_PMFNB] if 'integDur' in kwargs else None
        self.int_dur_noise_mf = kwargs['integDurMF'][SFTYPE_NOISE] if 'integDurMF' in kwargs else None
        self.int_dur_trans_mf = kwargs['integDurMF'][SFTYPE_TRANS] if 'integDurMF' in kwargs else None
        self.int_dur_absrx_mf = kwargs['integDurMF'][SFTYPE_ABSRX] if 'integDurMF' in kwargs else None
        self.int_dur_abstx_mf = kwargs['integDurMF'][SFTYPE_ABSTX] if 'integDurMF' in kwargs else None
        self.int_dur_absnb_mf = kwargs['integDurMF'][SFTYPE_ABSNB] if 'integDurMF' in kwargs else None
        self.int_dur_pmfnb_mf = kwargs['integDurMF'][SFTYPE_PMFNB] if 'integDurMF' in kwargs else None
        
        self.reset_dur_noise = kwargs['resetDur'][SFTYPE_NOISE] if 'resetDur' in kwargs else None
        self.reset_dur_trans = kwargs['resetDur'][SFTYPE_TRANS] if 'resetDur' in kwargs else None
        self.reset_dur_absrx = kwargs['resetDur'][SFTYPE_ABSRX] if 'resetDur' in kwargs else None
        self.reset_dur_abstx = kwargs['resetDur'][SFTYPE_ABSTX] if 'resetDur' in kwargs else None
        self.reset_dur_absnb = kwargs['resetDur'][SFTYPE_ABSNB] if 'resetDur' in kwargs else None
        self.reset_dur_pmfnb = kwargs['resetDur'][SFTYPE_PMFNB] if 'resetDur' in kwargs else None

        self.image_bursts_per_cluster_qf = kwargs['imageBurstsPerClusterQF'] if 'imageBurstsPerClusterQF' in kwargs else None
        self.image_bursts_per_cluster_mf = kwargs['imageBurstsPerClusterMF'] if 'imageBurstsPerClusterMF' in kwargs else None
        self.hybrid_x_bursts_per_cluster_qf = kwargs['hybridXBurstsPerClusterQF'][0] if 'hybridXBurstsPerClusterQF' in kwargs else None
        self.hybrid_x_bursts_per_cluster_mf = kwargs['hybridXBurstsPerClusterMF'][0] if 'hybridXBurstsPerClusterMF' in kwargs else None
        self.hybrid_y_bursts_per_cluster_qf = kwargs['hybridYBurstsPerClusterQF'][0] if 'hybridYBurstsPerClusterQF' in kwargs else None
        self.hybrid_y_bursts_per_cluster_mf = kwargs['hybridYBurstsPerClusterMF'][0] if 'hybridYBurstsPerClusterMF' in kwargs else None
        self.noise_bursts = kwargs['NoiseBursts'] if 'NoiseBursts' in kwargs else None

        self.subframe_num_clusters_noise = kwargs['superFrameConfs[0].sfReg2[1].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[1].subframeNumClusters' in kwargs else None
        self.subframe_num_clusters_trans = kwargs['superFrameConfs[0].sfReg2[2].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[2].subframeNumClusters' in kwargs else None
        self.subframe_num_clusters_absrx = kwargs['superFrameConfs[0].sfReg2[3].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[3].subframeNumClusters' in kwargs else None
        self.subframe_num_clusters_abstx = kwargs['superFrameConfs[0].sfReg2[4].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[4].subframeNumClusters' in kwargs else None
        self.subframe_num_clusters_absnb = kwargs['superFrameConfs[0].sfReg2[5].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[5].subframeNumClusters' in kwargs else None
        self.subframe_num_clusters_pmfnb  = kwargs['superFrameConfs[0].sfReg2[1].subframeNumClusters'] \
            if 'superFrameConfs[0].sfReg2[1].subframeNumClusters' in kwargs else None
        
        if 'extOscEnable' in kwargs and kwargs['extOscEnable'] == 1:
            self.average_clock = EXT_OSC_CLOCK
        else:
            self.average_clock = INTER_OSC_CLOCK

class FrameTimingVariables(object):
    def __init__(self, state_idx, is_freq_quiet, is_freq_multi):
        self.stretch_dur = None
        self.rstretch_dur = None
        self.burst_size1 = None
        self.burst_size2 = None
        self.filter_bandwidth = None
        self.disable_frequency = None
        self.str_name_prefix = self._create_var_prefix(state_idx, is_freq_quiet, is_freq_multi)

    def load(self, static_config, gear_idx):
        self.stretch_dur = static_config['{0}.{1}'.format(self.str_name_prefix, 'stretchDur')][gear_idx]
        self.rstretch_dur = static_config['{0}.{1}'.format(self.str_name_prefix, 'rstretchDur')][gear_idx]
        self.burst_size1 = static_config['{0}.{1}'.format(self.str_name_prefix, 'burstSize1')][gear_idx]
        self.burst_size2 = static_config['{0}.{1}'.format(self.str_name_prefix, 'burstSize2')][gear_idx]
        self.filter_bandwidth = static_config['{0}.{1}'.format( self.str_name_prefix, 'filtBW')][gear_idx]
        self.disable_frequency = static_config['{0}.{1}'.format(self.str_name_prefix, 'disableFreq')][gear_idx]

    def _create_var_prefix(self, state_idx, is_freq_quiet, is_freq_multi):
        if state_idx == STATE_TRANS_QF:
            return 'freqTable[0]'
        elif state_idx == STATE_TRANS_MF:
            return 'freqTable[3]'
        elif state_idx == STATE_HYBRID_X:
            if is_freq_quiet:
                return 'freqTable[1]'
            if is_freq_multi:
                return 'freqTable[4]'
        elif state_idx == STATE_HYBRID_Y:
            if is_freq_quiet:
                return 'freqTable[2]'
            if is_freq_multi:
                return 'freqTable[5]'             

class FrameTimingGear(object):
    def __init__(self, is_freq_quiet, is_freq_multi):
        self.is_freq_quiet = is_freq_quiet
        self.is_freq_multi = is_freq_multi
        self.is_used = False
        self.is_valid = False
        self.target_freq = None
        self.actual_freq = None
        self.target_report_rate = None
        self.actual_report_rate = None
        self.frame_report_rate = None
        self.frame_time = None
        self.frame_rate = None
        self.frame_period = None
        self.frame_idle = None
        self.frame_acquisition = None
        self.parameters = None
        self.variables_table = [FrameTimingVariables(0, self.is_freq_quiet, self.is_freq_multi) for i in range(NUM_STATES)]
        self.param_data = [FrameTimingGearParamData() for i in range(NUM_STATES)]
        self.gear_value = None # For display only

    # Create variables and param data of each state for specified gears
    def create(self, static_config, gear_idx):
        param_timing = FrameTimingParameters(**static_config)
        for state in range(len(self.variables_table)):
            vars_gear = FrameTimingVariables(state, self.is_freq_quiet, self.is_freq_multi)
            vars_gear.load(static_config, gear_idx)
            self.variables_table[state] = vars_gear

        for state in range(len(self.param_data)):
            data_gear = FrameTimingGearParamData()
            data_gear.load(param_timing, state, self.is_freq_quiet)
            self.param_data[state] = data_gear
            self.is_used = self.get_usage(self.variables_table)

    def get_usage(self, vars):
        if vars is not None:
            for vars_gear in self.variables_table:
                if vars_gear is not None:
                    is_used = vars_gear.disable_frequency == 0
                    if is_used:
                        return True
        return False

    def update_usage(self, is_used):
        if self.variables_table is not None:
            for vars_gear in self.variables_table:
                if vars_gear is not None:
                    vars_gear.disable_frequency = 0 if is_used else 1

class FrameTimingGearParamData(object):
    def __init__(self):
        self.int_dur = None
        self.reset_dur = None
        self.burst_per_cluster = None

    def load(self, param_frame, gear_state, is_freq_quiet):
        # get integration duration value
        if gear_state == STATE_TRANS_QF:
            self.int_dur = param_frame.image_int_dur
            self.reset_dur = param_frame.image_reset_dur
            self.burst_per_cluster = param_frame.image_bursts_per_cluster_qf
        elif gear_state == STATE_TRANS_MF:
            self.int_dur = param_frame.image_int_dur_mf
            self.reset_dur = param_frame.image_reset_dur
            self.burst_per_cluster = param_frame.image_bursts_per_cluster_mf
        elif gear_state == STATE_HYBRID_X:
            self.int_dur = param_frame.hybrid_int_dur
            self.reset_dur = param_frame.hybrid_reset_dur
            if is_freq_quiet == True:
                self.burst_per_cluster = param_frame.hybrid_x_bursts_per_cluster_qf
            else:
                self.burst_per_cluster = param_frame.hybrid_x_bursts_per_cluster_mf
        elif gear_state == STATE_HYBRID_Y:
            self.int_dur = param_frame.hybrid_int_dur
            self.reset_dur = param_frame.hybrid_reset_dur
            if is_freq_quiet == True:
                self.burst_per_cluster = param_frame.hybrid_y_bursts_per_cluster_qf
            else:
                self.burst_per_cluster = param_frame.hybrid_y_bursts_per_cluster_mf

class FrameTimingResult(object):
    def __init__(self):
        self.gear_quiet = FrameTimingGear(True, False)
        self.gear_multi = FrameTimingGear(False, True)

    def create(self, static_config, gear_idx):
        self.gear_quiet.create(static_config, gear_idx)
        self.gear_multi.create(static_config, gear_idx)

    def validate(self, is_freq_quiet, is_freq_multi):
        valid_gear = None
        if is_freq_quiet:
            valid_gear = self.gear_quiet
        else:
            valid_gear = self.gear_multi if is_freq_multi else None
        if valid_gear is not None:
            is_used = valid_gear.is_used
            if is_freq_quiet and is_used:
                self.gear_multi.is_used = True
            if is_freq_multi and not is_used:
                self.gear_quiet.is_used = False
            return True
        return False          