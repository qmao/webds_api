## DO NOT MODIFY
## 76c4f6433bc3c3ea54e0caf1498815d0456d13b1-1.0.0.6
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Force 0D Open - Guard Trace" description="Force 0D Open Test for Guard Trace (FPCA Only)"
# bin="31"
# product="S3908">
#       <parameter name="Limits" type="string[][]" description="Limits for Force 0D Open Test - Guard Trace"
#                   isoptional="false"
#                   islimit = "true"
#                   hint="Go to global settings to import test limit file." />
# </metadata>
##

from binascii import unhexlify
from struct import unpack

import Comm2Functions
import XMLTestResultGenerator


class ForceButtonOpenGuardPlane(object):
    def __init__(self):
        self.packet = Comm2Functions.Comm2DsCore.CreatePacket()

        self.message = ""
        self.result = False
        self.num_rows = None
        self.num_cols = None
        self.limit_matrix = []
        self.pass_fail_matrix = []  # 0 = pass, 1 = fail
        self.result_matrix = []
        self.failed_points = []
        self.sample_count = 0

        self.force_tx_count = 0
        self.force_rx_count = 0
        self.force_tx_mapping = []
        self.force_rx_mapping = []

        self.FORCE_TX_COUNT = "numForceTxs"
        self.FORCE_RX_COUNT = "numForceRxs"
        self.FORCE_TX_MAPPING = "forceTxes"
        self.FORCE_RX_MAPPING = "forceRxes"
        self.STATIC_CONFIGURATION = "staticConfiguration"
        self.PROD_REPORT_TYPE = 0x15

    @staticmethod
    def custom_range(byte_array):
        start = 0
        while start < len(byte_array):
            yield [byte_array[start], byte_array[start + 1]]
            start += 2

    def __convert_report_data(self, byte_array):
        """
        Takes raw data and converts to signed 16 bit report data
        :param byte_array: report data
        :return: converted array
        """
        # Trim to expected data
        data_len_row = self.num_rows * 2
        data_len_bytes = data_len_row * self.num_cols
        expected_array = byte_array[:data_len_bytes]
        converted_array = []
        indices = range(0, len(expected_array), 2)
        for i in indices:
            short_val = unpack("<h",
                               unhexlify(str('%02x' % expected_array[i]) + str('%02x' % expected_array[i + 1])))[0]
            converted_array.append(short_val)
        return converted_array

    def __get_static_var_value(self, var_name, packet):
        if packet is None or var_name is None:
            return None
        static_cfg_helper = Comm2Functions.Comm2DsCore_GetHelper(self.STATIC_CONFIGURATION)
        if static_cfg_helper is None:
            raise TestException("Missing static configuration packet helper.")

        ret_val = Comm2Functions.Comm2DsCore_GetVarValues(packet, self.STATIC_CONFIGURATION, var_name)
        if ret_val is None:
            raise TestException("Cannot read {0} variable.".format(str(var_name)))
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

    def __analyze_data(self):
        """
        Compares test data against limits
        :return:
        """
        if not self.result_matrix:
            raise TestException("No test results found.")

        self.pass_fail_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)

        Comm2Functions.ReportProgress(80)
        Comm2Functions.Trace("Checking result matrix against limits")
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):

                # if column not in self.force_tx_mapping and column not in self.force_rx_mapping:
                #     self.pass_fail_matrix[row][column] = -1
                #     continue

                if self.limit_matrix[row][column] == self.result_matrix[row][column]:
                    # row = rx
                    # column = tx
                    self.pass_fail_matrix[row][column] = 0
                else:
                    self.failed_points.append((str(column), str(row)))
                    self.pass_fail_matrix[row][column] = 1

        all_mapping = self.force_tx_mapping + self.force_rx_mapping
        all_mapping.sort()

        if self.failed_points:
            string_points = []
            for pnt in self.failed_points:
                col_pin = int(pnt[0])
                string_points.append("TRx".format(all_mapping[col_pin]))
            self.message = "Failed at: "
            self.message += ", ".join(string_points)

    def __get_input_params(self):
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
                    self.limit_matrix[row][column] = int(stripped_value)
                except ValueError:
                    stripped_value = str(Comm2Functions.GetInputParamEx("Limits", idx))[1:].strip("'").strip("\"")
                    self.limit_matrix[row][column] = int(stripped_value)
                    continue
        return True

    def __get_required_vars(self):
        """
        Gets numCols and numRows
        :return:
        """
        static_packet = Comm2Functions.Comm2DsCore.CreatePacket()

        try:
            if Comm2Functions.Comm2DsCore_ExecuteCommand(0x21, [], static_packet) != 0:
                raise TestException("Cannot read static configuration from device.")

            try:
                self.force_tx_count = self.__get_static_var_value(self.FORCE_TX_COUNT, static_packet)
                self.force_rx_count = self.__get_static_var_value(self.FORCE_RX_COUNT, static_packet)
            except TestException as e:
                if "Cannot read" in e.message or (self.force_tx_count is 0 and self.force_rx_count is 0):
                    raise TestException("Firmware does not support this production test.")

            static_cfg_helper = Comm2Functions.Comm2DsCore_GetHelper(self.STATIC_CONFIGURATION)
            if static_cfg_helper is None:
                raise TestException("Missing static configuration packet helper.")

            self.force_tx_mapping = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.STATIC_CONFIGURATION,
                                                             self.FORCE_TX_MAPPING)
            if self.force_tx_mapping is None:
                self.force_tx_mapping = []
            else:
                self.force_tx_mapping = self.force_tx_mapping[:self.force_tx_count]

            self.force_rx_mapping = Comm2Functions.Comm2DsCore_GetVarValues(static_packet, self.STATIC_CONFIGURATION,
                                                             self.FORCE_RX_MAPPING)
            if self.force_rx_mapping is None:
                self.force_rx_mapping = []
            else:
                self.force_rx_mapping = self.force_rx_mapping[:self.force_rx_count]

            self.num_rows = 1
            self.num_cols = self.force_tx_count + self.force_rx_count  # this is for the results grid

        finally:
            Comm2Functions.Comm2DsCore_DestroyPacket(static_packet)

    def __send_get_report(self):
        Comm2Functions.ReportProgress(40)
        Comm2Functions.Trace("Getting PID {0} test report...".format(self.PROD_REPORT_TYPE))
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.PROD_REPORT_TYPE], self.packet) != 0:
            raise TestException("Failed to receive Force 0D Open - Guard Trace test data from device.")
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
                self.result_matrix[row][column] = converted_array[i]
                i += 1

    def run(self):
        """
        Actually runs the Force 0D Open Test- Guard Trace
        :return:
        """

        self.__get_required_vars()
        self.__get_input_params()

        # col = tx, row = rx
        Comm2Functions.Trace("Creating result matrix...")
        self.result_matrix = Comm2Functions.CreateMatrix(self.num_cols, self.num_rows)
        self.__send_get_report()

        raw_data = self.packet.GetPayloadData()
        the_result = self.__convert_report_data(raw_data)

        self.__set_result_matrix(the_result)

        Comm2Functions.Trace("Analyzing data...")
        self.__analyze_data()

        if not self.message:
            self.result = True

    def cleanup(self):
        Comm2Functions.Comm2DsCore.DestroyPacket(self.packet)
        self.__reset()


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def main():
    Comm2Functions.Trace("Force 0D Open - Guard Trace STARTED")
    force_button_test = ForceButtonOpenGuardPlane()
    xml_generator = XMLTestResultGenerator.XMLTestResultGenerator()

    try:
        Comm2Functions.Trace("Running Force 0D Open - Guard Trace now...")
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
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        Comm2Functions.SetTestResult(False)
    except Exception as e:
        Comm2Functions.Trace(e)
        Comm2Functions.SetStringResult(e)
        Comm2Functions.SetTestResult(False)
    finally:
        Comm2Functions.Trace("Force Button Open Test - Guard Plane FINISHED")
        force_button_test.cleanup()
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
