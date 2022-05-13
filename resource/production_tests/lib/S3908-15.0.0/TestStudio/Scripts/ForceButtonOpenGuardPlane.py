## DO NOT MODIFY
## 21bdbd261bf088b98f9675f53b30e1af9acff545-1.0.0.9
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Force 0D Open - Guard Plane" description="Force 0D Open - Guard Plane (FPCA Only)"
# bin="27" product="S3908">
#       <parameter name="Limits" type="string[][]" description="Limits for Force 0D Open - Guard Plane"
#                   isoptional="false"
#                   islimit = "true"
#                   hint="Go to global settings to import test limit file." />
# </metadata>
##

from struct import unpack
from binascii import unhexlify
from time import sleep
import traceback

import Comm2Functions
import XMLTestResultGenerator


class ForceButtonOpenGuardPlane(object):
    def __init__(self):
        self.tx_count = "txCount"
        self.rx_count = "rxCount"
        self.force_tx_count_name = "numForceTxs"
        self.force_rx_count_name = "numForceRxs"
        self.force_tx_mapping_name = "forceTxes"
        self.force_rx_mapping_name = "forceRxes"
        self.force_LCBC = "ForceOpenTestLCBC"
        self.force_enable_test = "EnableForceOpenTest"
        self.enable_data_collection = "dataCollectionEn"
        self.static_config_name = "staticConfiguration"
        self.dynamic_config_name = "dynamicConfiguration"
        self.prod_report_type = 0x12

        self.packet = Comm2Functions.Comm2DsCore.CreatePacket()

        self.message = ""
        self.result = False
        self.num_rows = None
        self.num_cols = None
        self.limit_matrix = []
        self.pass_fail_matrix = []  # 0 = pass, 1 = fail
        self.lcbc0_matrix = []
        self.lcbc10_matrix = []
        self.result_matrix = []
        self.failed_points = []

        self.twoD_tx_count = 0
        self.twoD_rx_count = 0
        self.force_tx_count = 0
        self.force_rx_count = 0
        self.force_tx_mapping = []
        self.force_rx_mapping = []

    @staticmethod
    def __convert_report_data(raw_data, image_row_num, image_col_num, word_size=4):
        """
        Takes raw data byte array and converts to signed 32 bit report data
        Arguments:
            raw_data (bytearray): report data
            image_row_num (int): number of rows of output image
            image_col_num (int): number of columns of output image
            word_size (int): size of one word in bytes
        Return:
            list of unsigned int
        """
        if word_size != 4:
            raise TestException('currently only support 4-byte word size')
        # Trim to expected data
        data_len_row = image_row_num * word_size
        data_len_bytes = data_len_row * image_col_num
        expected_array = raw_data[:data_len_bytes]
        converted_array = []
        indices = range(0, len(expected_array), word_size)
        for i in indices:
            value_str = unhexlify('{0:02x}{1:02x}{2:02x}{3:02x}'.format(expected_array[i],
                                                                        expected_array[i + 1],
                                                                        expected_array[i + 2],
                                                                        expected_array[i + 3]))
            value = unpack("<i", value_str)[0]
            converted_array.append(value)
        return converted_array

    def __get_static_var_value(self, var_name, packet):
        if packet is None or var_name is None:
            return None
        static_cfg_helper = Comm2Functions.Comm2DsCore_GetHelper(self.static_config_name)
        if static_cfg_helper is None:
            raise TestException("Missing static configuration packet helper.")

        ret_val = Comm2Functions.Comm2DsCore_GetVarValues(packet, self.static_config_name, var_name)
        if ret_val is None:
            raise TestException("Cannot read {0} variable.".format(str(var_name)))
        Comm2Functions.Trace("{0} = {1}".format(str(ret_val[0]), var_name))
        return ret_val[0]

    @staticmethod
    def __reset():
        """
        Fires off reset command (0x04)
        :return:
        """
        packet = Comm2Functions.Comm2DsCore.CreatePacket()
        try:
            if Comm2Functions.Comm2DsCore.ExecuteCommand(4, [], packet) != 0:
                raise TestException("Cannot reset")
            fw_mode = Comm2Functions.Comm2DsCore.GetVarValues(packet, "identifyPacket_v0", "FirmwareMode")
            if fw_mode is None or len(fw_mode) != 1:
                raise TestException("Cannot get fw mode")
            if fw_mode[0] != 1:
                Comm2Functions.Trace('Detected that FW is not in APP mode == ' + str(fw_mode[0]))
                if Comm2Functions.Comm2DsCore.ExecuteCommand(0x14, [], packet) != 0:
                    raise TestException("Cannot run app command")
        finally:
            Comm2Functions.Comm2DsCore.DestroyPacket(packet)

    def __set_force_lcbc(self, dynamic_config, target_value):
        if dynamic_config is None:
            raise TestException(
                "Cannot set {0} to {1}.  No dynamic config packet given.".format(self.force_LCBC, target_value))

        Comm2Functions.Trace("Setting {0} to {1}...".format(self.force_LCBC, target_value))
        error_code = Comm2Functions.Comm2DsCore_SetVarValue(dynamic_config, self.dynamic_config_name, self.force_LCBC, target_value)
        if error_code != 0:
            Comm2Functions.Trace("error code {0}".format(error_code))
            raise TestException("Cannot set {0}".format(self.force_LCBC))

    def __enable_force_test(self, dynamic_config):
        if dynamic_config is None:
            raise TestException("Cannot set {0} to {1}.  No dynamic config packet given.".format(self.force_enable_test,
                                                                                                 1))

        Comm2Functions.Trace("Setting {0} to 1...".format(self.force_enable_test))
        error_code = Comm2Functions.Comm2DsCore_SetVarValue(dynamic_config, self.dynamic_config_name, self.force_enable_test, 1)
        if error_code != 0:
            Comm2Functions.Trace("error code {0}".format(error_code))
            raise TestException("Cannot set {0}".format(self.force_enable_test))

    def __enable_data_collection(self, static_config):
        if static_config is None:
            raise TestException("Cannot set {0} to {1}.  No static config packet given.".format(
                self.enable_data_collection, 1))

        Comm2Functions.Trace("Setting {0} to 1...".format(self.enable_data_collection))
        error_code = Comm2Functions.Comm2DsCore_SetVarValue(static_config, self.static_config_name, self.enable_data_collection, 1)
        if error_code != 0:
            Comm2Functions.Trace("error code {0}".format(error_code))
            raise TestException("Cannot set {0}".format(self.enable_data_collection))

    def __add_to_result_matrix(self, byte_array, target_matrix):
        i = 0
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                target_matrix[row][column] += byte_array[i]
                i += 1

    def __analyze_data(self):
        """
        Compares test data against limits
        :return:
        """
        if not self.result_matrix:
            raise TestException("No test results found.")

        mapping = self.force_rx_mapping + self.force_tx_mapping
        self.pass_fail_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)

        Comm2Functions.ReportProgress(80)
        Comm2Functions.Trace("Checking result matrix against limits")
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                if self.result_matrix[row][column] >= self.limit_matrix[row][column]:
                    # row = rx
                    # column = tx
                    self.pass_fail_matrix[row][column] = 1
                    self.failed_points.append((str(column), str(row)))
                else:
                    self.pass_fail_matrix[row][column] = 0

        if self.failed_points:
            string_points = []
            for pnt in self.failed_points:
                col_pin = int(pnt[0])
                string_points.append("Pin {0}".format(mapping[col_pin]))
            self.message = "Failed at: "
            self.message += ", ".join(string_points)

    def __calculate_delta(self, matrix_a, matrix_b):
        ret_val = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                ret_val[row][column] = matrix_a[row][column] - matrix_b[row][column]
        return ret_val

    def __get_input_params(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """

        Comm2Functions.Trace("Checking input params...")
        Comm2Functions.ReportProgress(10)

        Comm2Functions.Trace("Getting limits...")
        if Comm2Functions.GetInputParam("Limits") is None or Comm2Functions.GetInputDimension("Limits") is None:
            raise TestException("No test limits found.")

        Comm2Functions.Trace("Creating limit matrix...")
        self.limit_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                idx = Comm2Functions.GetInputIndex("Limits", [row, column])
                try:
                    stripped_value = str(Comm2Functions.GetInputParamEx("Limits", idx)).strip("'").strip("\"")
                    self.limit_matrix[row][column] = float(stripped_value)
                except ValueError:
                    stripped_value = str(Comm2Functions.GetInputParamEx("Limits", idx))[1:].strip("'").strip("\"")
                    self.limit_matrix[row][column] = float(stripped_value)
                    continue
        return True

    def __get_num_rows_cols(self):
        """
        Gets numCols and numRows
        :return:
        """
        static_packet = Comm2Functions.Comm2DsCore.CreatePacket()

        try:
            if Comm2Functions.Comm2DsCore_ExecuteCommand(0x21, [], static_packet) != 0:
                raise TestException("Cannot read static configuration from device.")

            self.twoD_tx_count = self.__get_static_var_value(self.tx_count, static_packet)
            self.twoD_rx_count = self.__get_static_var_value(self.rx_count, static_packet)

            try:
                self.force_tx_count = self.__get_static_var_value(self.force_tx_count_name, static_packet)
                self.force_rx_count = self.__get_static_var_value(self.force_rx_count_name, static_packet)
            except TestException as e:
                if "Cannot read" in e.message:
                    raise TestException("Firmware does not support this production test.")

            static_cfg_helper = Comm2Functions.Comm2DsCore_GetHelper(self.static_config_name)
            if static_cfg_helper is None:
                raise TestException("Missing static configuration packet helper.")

            self.force_tx_mapping = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.static_config_name,
                                                             self.force_tx_mapping_name)
            if self.force_tx_mapping is None:
                self.force_tx_mapping = []
            self.force_rx_mapping = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.static_config_name,
                                                             self.force_rx_mapping_name)
            if self.force_rx_mapping is None:
                self.force_rx_mapping = []

            self.num_rows = 1
            self.num_cols = self.force_rx_count + self.force_tx_count  # this is for the results grid

        finally:
            Comm2Functions.Comm2DsCore_DestroyPacket(static_packet)

    def __send_get_report(self):
        Comm2Functions.ReportProgress(40)
        Comm2Functions.Trace("Getting PID {0} test report...".format(self.prod_report_type))
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.prod_report_type], self.packet) != 0:
            raise TestException("Failed to receive Force 0D Open - Guard Plane test data from device.")
        # order coming in = receiver , force receiver, transmitter, force transmitter

    def __set_result_matrix(self, converted_array):
        """
        Sets report data to result matrix
        :param converted_array: converted array from report data
        :return:
        """
        i = 0
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                self.lcbc0_matrix[row][column] = converted_array[i]
                i += 1

    def run(self):
        """
        Actually runs the Force Button Test
        :return:
        """

        self.__get_num_rows_cols()
        self.__get_input_params()

        # col = tx, row = rx
        Comm2Functions.Trace("Creating result matrix...")
        self.lcbc0_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        self.lcbc10_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)

        # Check if we have static/dynamic config helper first before reading
        if Comm2Functions.Comm2DsCore_GetHelper(self.dynamic_config_name) is None:
            raise TestException("Missing dynamic configuration packet helper.")

        if Comm2Functions.Comm2DsCore_GetHelper(self.static_config_name) is None:
            raise TestException("Missing static configuration packet helper.")

        dynamic_config = Comm2Functions.Comm2DsCore_CreatePacket()
        static_config = Comm2Functions.Comm2DsCore_CreatePacket()

        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x21, [], static_config) != 0:
            raise TestException("Cannot read static configuration from device.")

        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x23, [0xff], dynamic_config) != 0:
            raise TestException("cannot read dynamic configuration from device.")

        try:
            first_report = self.__get_first_report(static_config, dynamic_config)
            second_report = self.__get_second_report(dynamic_config)

            # Trace("First report = {0}".format(first_report))
            # Trace("Second report = {0}".format(second_report))

            self.__add_to_result_matrix(first_report, self.lcbc0_matrix)
            self.__add_to_result_matrix(second_report, self.lcbc10_matrix)
        finally:
            Comm2Functions.Comm2DsCore_DestroyPacket(dynamic_config)
            Comm2Functions.Comm2DsCore_DestroyPacket(static_config)

        # zero lcbc image - 0x10 lcbc image
        self.result_matrix = self.__calculate_delta(self.lcbc0_matrix, self.lcbc10_matrix)

        Comm2Functions.Trace("Analyzing data...")
        self.__analyze_data()

        if not self.message:
            self.result = True

    def __get_first_report(self, static_config, dynamic_config):
        self.__enable_data_collection(static_config)
        self.__enable_force_test(dynamic_config)
        self.__set_force_lcbc(dynamic_config, 0)
        self.__commit_static_config(static_config)
        self.__commit_dynamic_config(dynamic_config)

        sleep(0.05)

        force_rx_array = []
        force_tx_array = []

        self.__send_get_report()
        raw_data = self.packet.GetPayloadData()
        if raw_data is not None:
            converted_data = self.__convert_report_data(raw_data, 1, self.twoD_tx_count + self.force_tx_count +
                                                        self.twoD_rx_count + self.force_rx_count)

            if self.force_rx_count:
                force_rx_array = converted_data[:self.twoD_rx_count - 1 + self.force_rx_count]

            half = converted_data[self.twoD_rx_count + self.force_rx_count:]

            if self.force_tx_count:
                force_tx_array = half[self.twoD_tx_count:]

        return [x / float(1000) for x in force_rx_array + force_tx_array]

    def __get_second_report(self, dynamic_config):
        self.__set_force_lcbc(dynamic_config, 0x0B)
        self.__commit_dynamic_config(dynamic_config)

        sleep(0.05)

        force_rx_array = []
        force_tx_array = []

        self.__send_get_report()
        raw_data = self.packet.GetPayloadData()
        if raw_data is not None:
            converted_data = self.__convert_report_data(raw_data, 1, self.twoD_tx_count + self.force_tx_count +
                                                        self.twoD_rx_count + self.force_rx_count)

            if self.force_rx_count:
                force_rx_array = converted_data[:self.twoD_rx_count - 1 + self.force_rx_count]

            half = converted_data[self.twoD_rx_count + self.force_rx_count:]

            if self.force_tx_count:
                force_tx_array = half[self.twoD_tx_count:]

        return [x / float(1000) for x in force_rx_array + force_tx_array]

    def __commit_static_config(self, static_config):
        if static_config is None:
            raise TestException("Cannot write static configuration; packet is empty.")

        if self.packet is None:
            self.packet = Comm2Functions.Comm2DsCore_CreatePacket()
        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x22, static_config.GetPayloadData(), self.packet) != 0:
            raise TestException("Cannot write static configuration to device.")

    def __commit_dynamic_config(self, dynamic_config):
        if dynamic_config is None:
            raise TestException("Cannot write dynamic configuration; packet is empty.")

        payload_to_send = list(dynamic_config.GetPayloadData())
        payload_to_send.insert(0, 0xff)

        if self.packet is None:
            self.packet = Comm2Functions.Comm2DsCore_CreatePacket()
        error_code = Comm2Functions.Comm2DsCore_ExecuteCommand(0x24, payload_to_send, self.packet)
        if error_code != 0:
            Comm2Functions.Trace("error code {0}".format(error_code))
            raise TestException("Cannot set dynamic configuration to device.")

    def cleanup(self):
        Comm2Functions.Comm2DsCore.DestroyPacket(self.packet)
        self.__reset()


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def main():
    trace_msg = None
    Comm2Functions.Trace("Force 0D Open - Guard Plane STARTED")
    force_button_test = ForceButtonOpenGuardPlane()
    xml_generator = XMLTestResultGenerator.XMLTestResultGenerator()

    try:
        Comm2Functions.Trace("Running Force 0D Open - Guard Plane now...")
        force_button_test.run()

        Comm2Functions.Trace("Creating custom xml")
        xml_generator.set_row_headers(["{0}".format(element) for element in range(0,
                                                                                   int(force_button_test.num_rows))])
        xml_generator.set_column_headers(["{0}".format(element) for element in range(0,
                                                                                      int(force_button_test.num_cols))])
        xml_generator.add_matrix(force_button_test.pass_fail_matrix,
                                 xml_generator.MATRIX_TYPE_LONG, "testResult")
        xml_generator.add_matrix(force_button_test.result_matrix,
                                 xml_generator.MATRIX_TYPE_DOUBLE, "rawData")
        xml_generator.add_matrix(force_button_test.limit_matrix,
                                 xml_generator.MATRIX_TYPE_CSV, "limits")

        Comm2Functions.SetCustomResult(str(xml_generator.get_xml()))
        Comm2Functions.SetStringResult(force_button_test.message)
        Comm2Functions.SetTestResult(force_button_test.result)

    except TestException as err:
        trace_msg = traceback.format_exc()
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        Comm2Functions.SetTestResult(False)
    except Exception as e:
        trace_msg = traceback.format_exc()
        Comm2Functions.Trace(e)
        Comm2Functions.SetStringResult(e)
        Comm2Functions.SetTestResult(False)
    finally:
        if trace_msg is not None:
            Comm2Functions.Trace(trace_msg)
        Comm2Functions.Trace("Force Button Open Test - Guard Plane FINISHED")
        force_button_test.cleanup()
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
