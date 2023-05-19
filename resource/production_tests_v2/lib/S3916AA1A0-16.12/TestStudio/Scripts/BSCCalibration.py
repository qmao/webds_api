## DO NOT MODIFY
## 0683a95534b7ffdac14d7575a379d3095b45d2f8-1.0.0.8
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="BSC Calibration Test" description="Baseline Shift Correction Calibration Test" bin="44"
# product="S3916A">
#       <parameter name="Timeout" type="double" hint="Timeout in milliseconds to wait for command execution"
#       description="Timeout (ms)"
#       isoptional="false">
#           <default>4000</default>
#       </parameter>
#       <parameter name="Sleep Period" type="double" hint="Sleep period in milliseconds to check for command
#       execution completion" description="Sleep Period (ms)"
#       isoptional="false">
#           <default>100</default>
#       </parameter>
# </metadata>
##

from datetime import datetime
from struct import pack, unpack, unpack_from
from binascii import unhexlify
from time import sleep
import traceback
import Comm2Functions
import XMLTestResultGenerator


class TestException(Exception):
    def __init__(self, message):
        self.message = message


class ReportBasedTest(object):
    def __init__(self):
        self.DEFAULT_TIMEOUT_MS = 4000
        self.DEFAULT_SLEEP_DELAY_MS = 100

        self._bit_per_pixel = 16
        self._data_collect_timeout = 10  # in seconds
        self._sample_count = 1
        self._report_id = 18  # default is RT18, delta cap image
        self._valid_data_collecting_type = ['delegate', 'production_test', 'diagnostic']
        self._data_collecting_type = 'delegate'
        self._name = ''
        self.message = ""
        self.result = False
        self.num_rows = None
        self.num_cols = None
        self.min_limit_matrix = None
        self.max_limit_matrix = None
        self.limit_matrix = None
        self.result_matrix = None
        self.pass_fail_matrix = None  # 0 = pass, 1 = fail
        self.failed_points = []
        self._compare_func_dict = {}
        self._report_data_converter = None
        self._image_process_funcs = []
        self._limit_desc = None
        self.static_packet = None
        self.timeout = None
        self.sleep = None

        self.rx_mapping = []
        self.tx_mapping = []

    @property
    def data_collect_timeout(self):
        """Get data collection timeout in seconds
        Returns:
            int -- Data collection timeout in seconds
        """
        return self._data_collect_timeout

    @data_collect_timeout.setter
    def data_collect_timeout(self, data_collect_timeout):
        self._data_collect_timeout = data_collect_timeout

    @property
    def report_id(self):
        return self._report_id

    @report_id.setter
    def report_id(self, report_id):
        self._report_id = report_id

    """Specify whether the report is a production test report.
       A production test report is the result of a certain kind of production test,
       and it is the response of production test command ($2A)
    """

    @property
    def data_collecting_type(self):
        return self._data_collecting_type

    @data_collecting_type.setter
    def data_collecting_type(self, val):
        if val.lower() in self._valid_data_collecting_type:
            self._data_collecting_type = val
        else:
            raise TestException('{0} is not a valid option'.format(val))

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def add_compare_func(self, limit_desc, func):
        """Add a function, which implements the logic to compare data with limit

        Arguments:
            limit_desc {string} -- 'single' or 'multiple'
            func {function} -- Function which implements the logic to compare data with limit
        """
        try:
            self._limit_desc = limit_desc.lower()
            if self._limit_desc == 'single' or self._limit_desc == 'multiple':
                self._compare_func_dict[self._limit_desc] = func
        except AttributeError as err:
            Comm2Functions.Trace('Add compare function failed. error message {}'.format(err))

    @property
    def report_data_converter(self):
        return self._report_data_converter

    @report_data_converter.setter
    def report_data_converter(self, converter):
        self._report_data_converter = converter

    @staticmethod
    def _default_report_data_converter(byte_array,
                                       image_row_num,
                                       image_col_num,
                                       word_size=2):
        """
        Takes raw data byte array and converts to signed 16 bit report data
        Arguments:
            byte_array (bytearray): report data
            image_row_num (int): number of rows of output image
            image_col_num (int): number of columns of output image
            word_size (int): size of one word in bytes
        Return:
            list of signed short
        """
        if word_size != 2:
            raise TestException('currently only support 2-byte word size')
        # Trim to expected data
        data_len_row = image_row_num * word_size
        data_len_bytes = data_len_row * image_col_num
        expected_array = byte_array[:data_len_bytes]
        converted_array = []
        indices = range(0, len(expected_array), word_size)
        for i in indices:
            short_val = unpack("<h",
                               unhexlify(str('%02x' % expected_array[i]) + str('%02x' % expected_array[i + 1])))[0]
            Comm2Functions.Trace("short_val = {0}".format(short_val))
            converted_array.append(short_val)

        return converted_array

    def add_image_process_func(self, func):
        self._image_process_funcs.append(func)

    def enable_diagnostic_reporting(self):
        """
        Fires off enable report command (0x05) for diag report
        :return:
        """
        packet = None
        try:
            Comm2Functions.Trace("Execute Enable Report 0x05 with payload of {}".format(self.report_id))
            packet = Comm2Functions.Comm2DsCore.CreatePacket()
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x05, [self.report_id], packet) != 0:
                raise TestException("Failed to enable report type {} reporting.".format(self.report_id))
        finally:
            if packet is not None:
                Comm2Functions.Comm2DsCore.DestroyPacket(packet)

    def disable_diagnostic_reporting(self):
        """
        Fires off disable report command (0x06) for diag report
        :return:
        """
        if self.data_collecting_type == 'production_test':
            return

        packet = None

        try:
            Comm2Functions.Trace("Execute Disable Report 0x06 with payload of {}".format(self.report_id))
            packet = Comm2Functions.Comm2DsCore.CreatePacket()
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x06, [self.report_id], packet) != 0:
                raise TestException("Failed to disable report type {} reporting.".format(self.report_id))
        finally:
            if packet is not None:
                Comm2Functions.Comm2DsCore.DestroyPacket(packet)

    def __get_num_row_cols(self):
        """
        Gets numCols and numRows from appInfoPacket
        :return:
        """
        self.num_rows = 1
        self.num_cols = 1

    def __setup(self):
        if self.data_collecting_type == 'production_test':
            return
        """
        Sets up FW to begin polling for report data
        :return:
        """
        if self.data_collecting_type == 'delegate':
            Comm2Functions.Comm2DsCore.SetCollectPacketInfo(self.name,
                                                            self.report_id,
                                                            self._sample_count)

    def apply_one_image_process_func(self, func):
        for i in range(0, len(self.result_matrix)):
            self.result_matrix[i] = map(func, self.result_matrix[i])

    def apply_image_process_funcs(self):
        if len(self.result_matrix) == 0:
            raise TestException('no result image')
        for i in range(0, len(self._image_process_funcs)):
            self.apply_one_image_process_func(self._image_process_funcs[i])

    """return one packet of report data. This is used to get diagnostic report
    """

    def poll_one_diagnostic_report_packet(self):
        if self.data_collecting_type != 'diagnostic':
            raise TestException('poll_diagnostic_report is not used to get report {0}'.format(self.report_id))
        Comm2Functions.ReportProgress(40)
        packet = Comm2Functions.Comm2DsCore.CreatePacket()
        Comm2Functions.Trace("Getting test report...")
        retry = 0
        read_packet_ret = -1
        already_dumped = False
        while retry < 10:
            read_packet_ret = Comm2Functions.Comm2DsCore.ReadPacket(packet)
            Comm2Functions.Trace('Read packet ret = {0}'.format(read_packet_ret))
            Comm2Functions.Trace('Packet report type = {0}'.format(packet.ReportType))
            if packet.ReportType == self._report_id and not already_dumped:
                Comm2Functions.Trace('Got report {0}'.format(self.report_id))
                Comm2Functions.Trace("Discarding to avoid stale report...")
                already_dumped = True
            elif packet.ReportType == self._report_id and already_dumped:
                Comm2Functions.Trace('Got report {0}'.format(self.report_id))
                break
            else:
                retry += 1
                read_packet_ret = -1

        if retry > 10 and read_packet_ret != 0:
            Comm2Functions.Trace("Failed to receive test data from device.")
        else:
            Comm2Functions.Trace('packet RT = {0}'.format(packet.ReportType))
            Comm2Functions.Trace('packet payload = {0}'.format(packet.PayLoadLength))
        return packet

    def get_one_production_test_response_packet(self):
        if self.data_collecting_type != 'production_test':
            raise TestException('get_production_test_report is not used to get report {0}'.format(self.report_id))
        Comm2Functions.ReportProgress(40)
        Comm2Functions.Trace("Getting test report PID = ${:02X}".format(self.report_id))
        packet = Comm2Functions.Comm2DsCore.CreatePacket()
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.report_id], packet) != 0:
            raise TestException("Failed to receive production test data from device.")
        return packet

    """
    get_delegation_result_packets() is delegating collecting of report to upper layer.
    """

    def get_delegation_result_packets(self):
        self.enable_diagnostic_reporting()
        Comm2Functions.Trace("Collecting report type {} samples...".format(self.report_id))
        try:
            if self.data_collecting_type != 'delegate':
                raise TestException(
                    'get_delegation_result_packets is not used to get report {0}'.format(self.report_id))
            start = datetime.now()
            total = 0
            count = 0
            while total < self.data_collect_timeout:
                # This just gives you the information on the collected packet information.
                # There could be a possibility that the collected packets does not equal the request packet count.
                count = Comm2Functions.Comm2DsCore.GetCollectPacketInfo(self.name)[0]
                if count == self._sample_count:
                    Comm2Functions.Trace("Collected " + str(self._sample_count) + " packets")
                    break
                total = (datetime.now() - start).total_seconds()

            if count == self._sample_count:
                collected_packets = []
                packet = Comm2Functions.Comm2DsCore.CreatePacket()
                for idx in range(self._sample_count):
                    correct_packet, timestamp = Comm2Functions.Comm2DsCore.GetCollectedPacket(self.name, idx, packet)
                    if not correct_packet:
                        Comm2Functions.Trace("Incorrect Packet")
                        raise TestException('Got packets back, but they are not what we requested!')
                    if idx == self._sample_count - 1:
                        Comm2Functions.Trace("Only accepting second report to avoid stale report data.")
                        collected_packets.append(packet)
                return collected_packets
            else:
                Comm2Functions.Trace("collected " + str(count) + " packet(s)")
                raise TestException("Cannot obtain requested number of samples")
        finally:
            self.disable_diagnostic_reporting()

    def get_packets(self):
        if self.data_collecting_type == 'delegate':
            return self.get_delegation_result_packets()
        else:
            if self.data_collecting_type == 'production_test':
                packet_getter = self.get_one_production_test_response_packet
            else:
                packet_getter = self.poll_one_diagnostic_report_packet
            count = 0
            packets = []
            while count < self._sample_count:
                packets.append(packet_getter())
                count += 1
            return packets

    def map_packets_to_matrices(self, packets):
        matrices = map(lambda p: self.data_byte_array_to_matrix(p.GetPayloadData()),
                       packets)
        return matrices

    @staticmethod
    def reduce_matrices(matricesMap):
        matrices = list(matricesMap)
        if len(matrices) == 0:
            raise TestException('no any packet available in list')
        if len(matrices) > 1:
            raise TestException('more than one packet is in the list')
        return matrices[0]

    def __calibrate_bsc(self):
        temp_packet = None
        try:
            temp_packet = Comm2Functions.Comm2DsCore_CreatePacket()

            Comm2Functions.Trace("Executing erase command...")
            if Comm2Functions.Comm2DsCore_ExecuteCommand(0x33, [3], temp_packet) != 0:
                raise TestException("Failed to erase BSC calibration area.")

            sleep(1)

            Comm2Functions.Trace("Executing calibration command...")
            Comm2Functions.Trace("Waiting total of {0} ms, checking every {1} ms".format(self.timeout, self.sleep))
            if Comm2Functions.Comm2DsCore_ExecuteCommandEx(0x33, [2], temp_packet, self.timeout, self.sleep) != 0:
                raise TestException("Failed to calibrate BSC.")

        finally:
            if temp_packet is not None:
                Comm2Functions.Comm2DsCore_DestroyPacket(temp_packet)

    def run(self):
        packets = None
        try:
            self.__calibrate_bsc()
            self.__setup()
            packets = self.get_packets()
            matrices = self.map_packets_to_matrices(packets)
            Comm2Functions.Trace("Creating result matrix...")
            self.result_matrix = self.reduce_matrices(matrices)
            self.apply_image_process_funcs()
            self.analyze_data()
            Comm2Functions.ReportProgress(60)

        finally:
            if packets is not None:
                # clean up packets that are no longer needed
                for packet in packets:
                    Comm2Functions.Comm2DsCore.DestroyPacket(packet)
                Comm2Functions.Trace("packets no longer needed are cleanup.")

    def data_byte_array_to_matrix(self, byte_array):
        payload_len = len(byte_array)
        data_len_row = self.num_rows * 2
        data_len_bytes = data_len_row * self.num_cols
        expected_array = byte_array[:data_len_bytes]
        if payload_len < data_len_bytes:
            err_str = 'Expect {0} bytes of payload, but only got {1}'.format(data_len_bytes,
                                                                             payload_len)
            Comm2Functions.Trace(err_str)
            raise TestException(err_str)
        elif payload_len > len(expected_array):
            warning_str = 'Expect {0} bytes of payload, got {1}. More than expected'.format(data_len_bytes,
                                                                                            payload_len)
            Comm2Functions.Trace(warning_str)
        else:
            good_str = 'Expect {0} bytes of payload, got {1}.'.format(data_len_bytes, payload_len)
            Comm2Functions.Trace(good_str)
        converted_array = self.convert_report_data(byte_array)
        matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        Comm2Functions.Trace("Adding frame to result matrix")
        i = 0
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                matrix[row][column] = converted_array[i]
                i += 1
        return matrix

    def convert_report_data(self, byte_array):
        if self._report_data_converter is None:
            self._report_data_converter = self._default_report_data_converter
        return self._report_data_converter(byte_array=byte_array,
                                           image_row_num=self.num_rows,
                                           image_col_num=self.num_cols,
                                           word_size=int(self._bit_per_pixel / 8))

    def analyze_data(self):
        if not self.result_matrix:
            raise TestException("No test results found.")

        # 0 = fail
        # 1 = pass
        self.result = self.result_matrix[0][0] is 1

    def prepare_single_limit_matrix(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """
        Comm2Functions.Trace("Creating limit matrix...")
        self.limit_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                self.limit_matrix[row][column] = 0
        return True

    def prepare_multiple_limit_matrix(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """

        Comm2Functions.Trace("Getting limits...")
        if Comm2Functions.GetInputParam("Limits") is None:
            raise TestException("No limits found.")
        limit_dim = Comm2Functions.GetInputDimension("Limits")

        if limit_dim is None:
            raise TestException("No test limits provided.")

        Comm2Functions.Trace("Creating min limit matrix...")

        self.min_limit_matrix = Comm2Functions.CreateMatrix(limit_dim[1], limit_dim[0])

        Comm2Functions.Trace("Creating max limit matrix...")
        self.max_limit_matrix = Comm2Functions.CreateMatrix(limit_dim[1], limit_dim[0])

        Comm2Functions.Trace("Creating combined limit matrix...")
        self.limit_matrix = Comm2Functions.CreateMatrix(limit_dim[1], limit_dim[0])

        for row in range(0, limit_dim[0]):
            for column in range(0, limit_dim[1]):
                idx = Comm2Functions.GetInputIndex("Limits", [row, column])
                try:
                    raw_data = str(Comm2Functions.GetInputParamEx("Limits", idx)).split(":")
                    min_val = raw_data[0].strip("'").strip("\"")
                    max_val = raw_data[1].strip("'").strip("\"")
                    self.limit_matrix[row][column] = "{0} - {1}".format(min_val, max_val)
                    self.min_limit_matrix[row][column] = int(min_val)
                    self.max_limit_matrix[row][column] = int(max_val)
                except ValueError:
                    raw_data = Comm2Functions.GetInputParamEx("Limits", idx)[2:-1].split(":")
                    min_val = int(raw_data[0])
                    max_val = int(raw_data[1])
                    self.limit_matrix[row][column] = "{0} - {1}".format(min_val, max_val)
                    self.min_limit_matrix[row][column] = min_val
                    self.max_limit_matrix[row][column] = max_val
                    continue
        return True

    def get_input_params(self):
        self.__get_num_row_cols()
        timeout = Comm2Functions.GetInputParam("Timeout")
        if timeout is None:
            Comm2Functions.Trace("Cannot find valid timeout period; using default timeout period of {0} ms.".format(
                self.DEFAULT_TIMEOUT_MS))
            self.timeout = int(self.DEFAULT_TIMEOUT_MS)
        else:
            self.timeout = int(timeout[0])

        sleep_time = Comm2Functions.GetInputParam("Sleep Period")
        if sleep_time is None:
            Comm2Functions.Trace("Cannot find valid sleep period; using default sleep period of {0} ms.".format(
                self.DEFAULT_SLEEP_DELAY_MS))
            self.sleep = int(self.DEFAULT_SLEEP_DELAY_MS)
        else:
            self.sleep = int(sleep_time[0])

        return True


def judgement_func(**kwargs):
    try:
        data = kwargs.pop('data', 0)
        limit = kwargs.pop('limit', 0)
        row_size = kwargs.pop('row_size', 0)
        col_size = kwargs.pop('col_size', 0)
        current_row = kwargs.pop('current_row', 0)
        current_col = kwargs.pop('current_col', 0)
    except KeyError as key_err:
        raise key_err
    if kwargs:
        raise TypeError('Unexpected **kwargs: %r' % kwargs)
    if int(data) > int(limit):
        return True
    return False


def int32_to_uint32(i):
    return unpack_from("I", pack("i", i))[0]


def main():
    track_back_msg = None
    Comm2Functions.Trace("Test STARTED")
    test = ReportBasedTest()
    test.data_collect_timeout = 10
    test.report_id = 0x1E
    test.name = 'BSC Calibration Test'
    test.data_collecting_type = 'production_test'

    try:
        Comm2Functions.Trace("Checking input params")
        Comm2Functions.ReportProgress(10)
        if not test.get_input_params():
            raise TestException("Invalid input parameters")

        Comm2Functions.Trace("Running {} test now...".format(test.name))
        test.run()

        Comm2Functions.Trace("Creating custom xml")
        Comm2Functions.SetStringResult(test.message)
        Comm2Functions.SetTestResult(test.result)
    except TestException as err:
        track_back_msg = traceback.format_exc()
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        Comm2Functions.SetTestResult(False)
    except Exception as exp:
        track_back_msg = traceback.format_exc()
        Comm2Functions.Trace(exp)
        Comm2Functions.SetStringResult(exp)
        Comm2Functions.SetTestResult(False)
    finally:
        if track_back_msg is not None:
            Comm2Functions.Trace(track_back_msg)
        Comm2Functions.Trace("Test FINISHED")
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
