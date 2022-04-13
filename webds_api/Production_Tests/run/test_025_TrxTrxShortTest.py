## DO NOT MODIFY
## 3f36497e0c462f27ca26fd79d4d6032652641bff-1.0.0.10
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Trx Trx Short Test" description="Trx Trx Short (FPCA Only)" bin="22" product="S3908">
#       <parameter name="Limits" type="string[][]" description="Limits for Trx Trx Short Test"
#                   isoptional="false"
#                   islimit = "true"
#                   hint="Go to global settings to import test limit file." />
# </metadata>
##
from datetime import datetime
from struct import unpack
from binascii import unhexlify
from time import sleep
import traceback
import math
import Comm2Functions
import XMLTestResultGenerator


class TestException(Exception):
    def __init__(self, message):
        self.message = message


class ReportBasedTest(object):
    def __init__(self):
        self.IMAGE_TXES = "imageTxes"
        self.IMAGE_RXES = "imageRxes"
        self.STATIC_CONFIGURATION = "staticConfiguration"
        self.MAX_TRX = 61
        self.BIT_PER_PIXEL = 16
        self.NAME = 'TRx Trx Short Test'
        self.REPORT_ID = 0x01
        self.DATA_COLLECTION_TYPE = 'production_test'

        self._data_collect_timeout = 10  # in seconds
        self._sample_count = 1
        self._valid_data_collecting_type = ['delegate', 'production_test', 'diagnostic']

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

        # static config vars
        self.tx_mapping = []
        self.rx_mapping = []

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
        return self.REPORT_ID

    @report_id.setter
    def report_id(self, report_id):
        self.REPORT_ID = report_id

    """Specify whether the report is a production test report.
       A production test report is the result of a certain kind of production test,
       and it is the response of production test command ($2A)
    """

    @property
    def data_collecting_type(self):
        return self.DATA_COLLECTION_TYPE

    @data_collecting_type.setter
    def data_collecting_type(self, val):
        if val.lower() in self._valid_data_collecting_type:
            self.DATA_COLLECTION_TYPE = val
        else:
            raise TestException('{0} is not a valid option'.format(val))

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
                                       word_size=1):
        """
        Takes raw data byte array and converts to unsigned 8 bit report data
        Arguments:
            byte_array (bytearray): report data
            image_row_num (int): number of rows of output image
            image_col_num (int): number of columns of output image
            word_size (int): size of one word in bytes
        Return:
            list of signed short
        """
        # Trim to expected data
        data_len_bytes = int(math.ceil(float(image_row_num + image_col_num) / float(8)))
        expected_array = byte_array[:data_len_bytes]
        converted_array = []
        indices = range(0, len(expected_array))
        for i in indices:
            short_val = unpack("<B", unhexlify(str('%02x' % expected_array[i])))[0]
            converted_array.append(short_val)

        binary_array = []
        temp = []
        for char in converted_array:
            del temp[:]
            temp.append(str("{0:08b}".format(char))[::-1])
            for x in range(len(temp[0])):
                binary_array.append(int(temp[0][x]))

        return binary_array

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

    def get_app_info(self):
        """
        Gets numCols and numRows from appInfoPacket
        :return:
        """
        self.num_cols = self.MAX_TRX
        self.num_rows = 1

    def setup(self):
        if self.data_collecting_type == 'production_test':
            return
        """
        Sets up FW to begin polling for report data
        :return:
        """
        self.enable_diagnostic_reporting()
        Comm2Functions.Trace("Collecting report type {} samples...".format(self.report_id))
        if self.data_collecting_type == 'delegate':
            Comm2Functions.Comm2DsCore.SetCollectPacketInfo(self.NAME,
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
        while retry < 10:
            read_packet_ret = Comm2Functions.Comm2DsCore.ReadPacket(packet)
            Comm2Functions.Trace('Read packet ret = {0}'.format(read_packet_ret))
            Comm2Functions.Trace('Packet report type = {0}'.format(packet.ReportType))
            if packet.ReportType == self.REPORT_ID:
                Comm2Functions.Trace('Got report {0}'.format(self.report_id))
                break
            else:
                retry += 1
                sleep(0.5)

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
        try:
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.report_id], packet) != 0:
                raise TestException("Failed to receive production test data from device.")
            return packet
        except Exception as e:
            Comm2Functions.Comm2DsCore_DestroyPacket(packet)
            raise e

    def get_delegation_result_packets(self):
        """
        get_delegation_result_packets() is delegating collecting of report to upper layer.
        :return:
        """
        if self.data_collecting_type != 'delegate':
            raise TestException('get_delegation_result_packets is not used to get report {0}'.format(self.report_id))
        start = datetime.now()
        total = 0
        count = None
        while total < self.data_collect_timeout:
            # This just gives you the information on the collected packet information.
            # There could be a possibility that the collected packets does not equal the request packet count.
            count = Comm2Functions.Comm2DsCore.GetCollectPacketInfo(self.NAME)[0]
            if count == self._sample_count:
                Comm2Functions.Trace("Collected " + str(self._sample_count) + " packets")
                break
            total = (datetime.now() - start).total_seconds()

        if count == self._sample_count:
            collected_packets = []
            packet = Comm2Functions.Comm2DsCore.CreatePacket()
            try:
                for idx in range(self._sample_count):
                    correct_packet, timestamp = Comm2Functions.Comm2DsCore.GetCollectedPacket(self.NAME, idx, packet)
                    if not correct_packet:
                        Comm2Functions.Trace("Incorrect Packet")
                        raise TestException('Got packets back, but they are not what we requested!')
                    collected_packets.append(packet)
                return collected_packets
            except Exception as e:
                Comm2Functions.Comm2DsCore_DestroyPacket(packet)
                raise e
        else:
            Comm2Functions.Trace("collected " + str(count) + " packet(s)")
            raise TestException("Cannot obtain requested number of samples")

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

    def __read_static_vars(self):
        # Check if we have static config helper first before reading
        if Comm2Functions.Comm2DsCore_GetHelper(self.STATIC_CONFIGURATION) is None:
            raise TestException("Missing static configuration packet helper.")

        try:
            static_packet = Comm2Functions.Comm2DsCore_CreatePacket()
            if Comm2Functions.Comm2DsCore_ExecuteCommand(0x21, [], static_packet) != 0:
                raise TestException("Cannot read static configuration from device.")
            else:
                image_rxes = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.STATIC_CONFIGURATION, self.IMAGE_RXES)
                if image_rxes is not None:
                    self.rx_mapping = image_rxes
                image_txes = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.STATIC_CONFIGURATION, self.IMAGE_TXES)
                if image_txes is not None:
                    self.tx_mapping = image_txes
        except Exception as te:
            raise te
        finally:
            if static_packet is not None:
                Comm2Functions.Comm2DsCore_DestroyPacket(static_packet)

    def run(self):
        packets = None
        try:
            self.get_app_info()
            self.__read_static_vars()
            self.setup()
            packets = self.get_packets()
            matrices = self.map_packets_to_matrices(packets)
            Comm2Functions.Trace("Creating result matrix...")
            self.result_matrix = self.reduce_matrices(matrices)
            self.apply_image_process_funcs()
            self.analyze_data()
            Comm2Functions.ReportProgress(60)

            if not self.message:
                self.result = True
        finally:
            if packets is not None:
                # clean up packets that are no longer needed
                for packet in packets:
                    Comm2Functions.Comm2DsCore.DestroyPacket(packet)
            Comm2Functions.Trace("packets no longer needed are cleanup.")

    def data_byte_array_to_matrix(self, byte_array):
        payload_len = len(byte_array)
        expected_len = int(math.ceil(float(self.num_cols) / float(8)))
        if payload_len < expected_len:
            err_str = 'Expect {0} bytes of payload, but only got {1}'.format(expected_len,
                                                                             payload_len)
            Comm2Functions.Trace(err_str)
            raise TestException(err_str)
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
                                           word_size=int(self.BIT_PER_PIXEL / 8))

    def analyze_data(self):
        if not self.result_matrix:
            raise TestException("No test results found.")

        self.pass_fail_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        Comm2Functions.ReportProgress(80)
        Comm2Functions.Trace("Checking result matrix against limits")
        compare_func = None
        try:
            compare_func = self._compare_func_dict[self._limit_desc]
        except KeyError as err:
            Comm2Functions.Trace(err.message)
            compare_func = None
        finally:
            if compare_func is None:
                raise TestException('no compare logic function!')
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                if self._limit_desc == 'single':
                    compare_result = compare_func(data=self.result_matrix[row][column],
                                                  limit=self.limit_matrix[row][column])
                else:
                    compare_result = compare_func(data=self.result_matrix[row][column],
                                                  limit_lower=self.min_limit_matrix[row][column],
                                                  limit_upper=self.max_limit_matrix[row][column])

                if column not in self.tx_mapping and column not in self.rx_mapping and column is not 60:
                    self.pass_fail_matrix[row][column] = -1
                    continue

                if compare_result:
                    # row = rx
                    # column = tx
                    self.pass_fail_matrix[row][column] = 1
                    self.failed_points.append((str(column), str(row)))
                else:
                    self.pass_fail_matrix[row][column] = 0

        if self.failed_points:
            string_points = []
            for pnt in self.failed_points:
                col_pin = pnt[0]
                if int(col_pin) is 60:
                    string_points.append("VGUARD")
                else:
                    string_points.append("TRx{0}".format(col_pin))
            self.message = "Failed at: "
            self.message += ", ".join(string_points)
    def prepare_single_limit_matrix(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """
        # Row first then column
        if Comm2Functions.GetInputParam("Limits") is None:
            raise TestException("No limits found.")

        limit_dim = Comm2Functions.GetInputDimension("Limits")
        Comm2Functions.GetInputParam("Limits")

        Comm2Functions.Trace("Creating limit matrix...")
        self.limit_matrix = Comm2Functions.CreateMatrix(limit_dim[1], limit_dim[0])
        for row in range(0, limit_dim[0]):
            for column in range(0, limit_dim[1]):
                idx = Comm2Functions.GetInputIndex("Limits", [row, column])
                try:
                    stripped_value = str(Comm2Functions.GetInputParamEx("Limits", idx)).strip("'").strip("\"")
                    self.limit_matrix[row][column] = float(stripped_value)
                except ValueError:
                    stripped_value = str(Comm2Functions.GetInputParamEx("Limits", idx))[1:].strip("'").strip("\"")
                    self.limit_matrix[row][column] = float(stripped_value)
                    continue
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
        # Limit format is min,max; default limits are 250,750
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
        if self._limit_desc == 'multiple':
            return self.prepare_multiple_limit_matrix()
        else:
            return self.prepare_single_limit_matrix()


def judgement_func(**kwargs):
    """
    return true if failure
    :param kwargs:
    :return:
    """
    try:
        data = kwargs.pop('data', 0)
        limit = kwargs.pop('limit', 0)
    except KeyError as key_err:
        raise key_err
    if kwargs:
        raise TypeError('Unexpected **kwargs: %r' % kwargs)
    if int(data) != int(limit):
        return True
    return False


def main():
    track_back_msg = None
    Comm2Functions.Trace("Test STARTED")
    test = ReportBasedTest()
    test.add_compare_func('single', judgement_func)
    xml_generator = XMLTestResultGenerator.XMLTestResultGenerator()

    try:
        Comm2Functions.Trace("Checking input params")
        Comm2Functions.ReportProgress(10)
        if not test.get_input_params():
            raise TestException("Invalid input parameters")

        Comm2Functions.Trace("Running {} test now...".format(test.NAME))
        test.run()

        Comm2Functions.Trace("Creating custom xml")
        xml_generator.set_row_headers(["{0}".format(element) for element in range(0, int(test.num_rows))])
        xml_generator.set_column_headers(["{0}".format(element) for element in range(0, int(test.num_cols))])
        xml_generator.add_matrix(test.pass_fail_matrix,
                                 xml_generator.MATRIX_TYPE_LONG,
                                 "testResult")
        xml_generator.add_matrix(test.result_matrix,
                                 xml_generator.MATRIX_TYPE_DOUBLE,
                                 "rawData")
        xml_generator.add_matrix(test.limit_matrix,
                                 xml_generator.MATRIX_TYPE_CSV,
                                 "limits")

        Comm2Functions.SetCustomResult(str(xml_generator.get_xml()))
        Comm2Functions.SetStringResult(test.message)
        Comm2Functions.SetTestResult(test.result)
        test.disable_diagnostic_reporting()
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

def test_main():
    main()
    assert Comm2Functions.GetTestResult() == True, 'Test failed'