## DO NOT MODIFY
## 38a033ab94df08dff68592892f214de3308e89ec-1.0.0.11
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Extended High Resistance Test" description="Extended High Resistance Test" bin="25" product="S3908">
#       <parameter name="Limits" type="string[][]" description="Limits for Extended High Resistance Test"
#                   isoptional="false"
#                   islimit = "true"
#                   hint="Go to global settings to import test limit file." />
#       <parameter name="References" type="double[]" isRefImage="true"
#                   description="Reference data file"
#                   hint="Data size should match device's tx/rx count."
#                   isoptional="false"/>
# </metadata>
##

import sys
import os
import os.path
import traceback
import ctypes
from struct import unpack
from binascii import unhexlify

import Comm2Functions
import XMLTestResultGenerator


class ExtendedHighResistance(object):
    class ExtHgResData(ctypes.Structure):
        _fields_ = [("TxCt", ctypes.c_int32),
                    ("RxCt", ctypes.c_int32),
                    ("delt", ctypes.POINTER(ctypes.POINTER(ctypes.c_float))),
                    ("base", ctypes.POINTER(ctypes.POINTER(ctypes.c_float))),
                    ("refe", ctypes.POINTER(ctypes.POINTER(ctypes.c_float))),
                    ("resu", ctypes.POINTER(ctypes.POINTER(ctypes.c_float)))]

    def __init__(self):
        self.BIT_PER_PIXEL = 16
        self.REPORT_ID = 0x5
        self.TRX_MAX = 40

        self.baseDir = ""
        self.packet = Comm2Functions.Comm2DsCore.CreatePacket()
        self.touch_info_packet = None
        self.message = ""
        self.result = False
        self.num_rows = None
        self.num_cols = None
        self.limit_matrix = []
        self.min_limit_matrix = []
        self.max_limit_matrix = []
        self.pass_fail_matrix = []  # 0 = pass, 1 = fail
        self.result_matrix = []
        self.failed_points = []
        self.Reference = None
        self.Delta = None
        self.Baseline = None
        self.Result = None
        self.lib = None

    def init(self):
        self.baseDir = os.path.dirname(os.path.abspath(sys.path[0])) + "\\TestStudio\\"
        ###
        # Load the production test dll Extended_High_Resistance.dll.
        ###
        pypath = self.baseDir + "Extended_High_Resistance.dll"

        if os.path.isfile(pypath):
            Comm2Functions.Trace("Loading " + pypath + " ...")
            self.lib = ctypes.cdll.LoadLibrary(pypath)
            Comm2Functions.Trace("... loaded.")
        else:
            raise TestException("\"" + pypath + "\" is not found.")

        ###
        # Declare function prototype according to the Extended_High_Resistance.h
        ###
        self.lib.allocate2DArray.argtypes = [ctypes.c_int32, ctypes.c_int32]
        self.lib.allocate2DArray.restype = ctypes.POINTER(ctypes.POINTER(ctypes.c_float))

        self.lib.free2DArray.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), ctypes.c_int32]
        self.lib.free2DArray.restype = None

        self.lib.fnExtended_High_Resistance.argtypes = [self.ExtHgResData]
        self.lib.fnExtended_High_Resistance.restype = None

    @staticmethod
    def custom_range(byte_array):
        start = 0
        while start < len(byte_array):
            yield [byte_array[start], byte_array[start + 1]]
            start += 2

    def get_static_config_info(self):
        """
        Gets numTx and numRx from static config packet
        :return:
        """
        static_packet = Comm2Functions.Comm2DsCore.CreatePacket()

        try:
            if Comm2Functions.Comm2DsCore_GetHelper("staticConfiguration") is None:
                raise TestException("Missing static configuration packet helper.")

            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x21, [], static_packet) != 0:
                raise TestException("Cannot get static config packet from device.")
            else:
                # Rows = Tx
                # Col = Rx

                temp = Comm2Functions.Comm2DsCore.GetVarValues(static_packet, "staticConfiguration", "rxCount")
                if temp is None or len(temp) != 1:
                    raise TestException("Failed to get rx count from device.")
                self.num_cols = temp[0]
                Comm2Functions.Trace("Number of columns (rxCount): %d" % self.num_cols)

                temp = Comm2Functions.Comm2DsCore.GetVarValues(static_packet, "staticConfiguration", "txCount")
                if temp is None or len(temp) != 1:
                    raise TestException("Failed to get tx count from device.")
                self.num_rows = temp[0]
                Comm2Functions.Trace("Number of rows (txCount): %d" % self.num_rows)
        finally:
            Comm2Functions.Comm2DsCore.DestroyPacket(static_packet)

    def send_get_report(self):
        Comm2Functions.ReportProgress(40)
        Comm2Functions.Trace("Getting test report...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.REPORT_ID], self.packet) != 0:
            raise TestException("Failed to receive Extended High Resistance test data from device.")

    def get_touch_info(self):
        if self.touch_info_packet is None:
            self.touch_info_packet = Comm2Functions.Comm2DsCore.CreatePacket()
        if self.touch_info_packet.PayLoadLength == 0:
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2e, [], self.touch_info_packet) != 0:
                raise TestException("Cannot get touch info packet from device.")

    def convert_report_data(self, byte_array, data_dump):
        """
        Takes raw data and converts to signed 16 bit report data
        :param data_dump:
        :param byte_array: report data
        :return: converted array
        """
        # Trim to expected data
        data_len_row = int(self.num_rows * self.BIT_PER_PIXEL / 8)
        data_len_bytes = data_len_row * self.num_cols
        expected_array = byte_array[:data_len_bytes]

        converted_array = []
        for x in ExtendedHighResistance.custom_range(expected_array):
            # zero padding
            # < = little endian (> = big endian)
            # h = signed short (H = unsigned short)
            short_val = unpack("<h", unhexlify(str('%02x' % x[0]) + str('%02x' % x[1])))[0]
            converted_array.append(short_val / 1000.0)
            # from_bytes only available in Python 3
            # int_val = int.from_bytes(x, byteorder='big', signed=False)

        if data_dump:
            idx = 0
            Comm2Functions.Trace("Production ID data: (raw length " +
                  str(len(expected_array)) + "), (data length " + str(len(converted_array)) + ")")
            for ii in range(0, self.num_rows):
                row_buf = "row " + "%2d" % ii + ": "
                for jj in range(0, self.num_cols):
                    if jj > 0:
                        row_buf = row_buf + ", "
                    row_buf = row_buf + "%.3f" % float(converted_array[idx])
                    idx += 1
                Comm2Functions.Trace(row_buf)

        return converted_array

    def set_result_matrix(self, data_dump):
        """
        Sets report data to result matrix
        :return:
        """
        if data_dump:
            Comm2Functions.Trace("EHR algo Result:")
            for ii in range(0, self.num_rows + 1):
                row_buf = "row " + "%2d" % ii + ": "
                for jj in range(0, self.num_cols + 1):
                    if jj > 0:
                        row_buf = row_buf + ", "
                    row_buf = row_buf + "%.3f" % float(self.Result[ii][jj])
                Comm2Functions.Trace(row_buf)

        for row in range(0, self.num_rows + 1):
            for column in range(0, self.num_cols + 1):
                self.result_matrix[row][column] = float(self.Result[row][column])

    ###
    ### Compare Extended_High_Resistance test limits
    ###
    def analyze_data(self):
        """
        Compares test data against limits
        :return:
        """
        if not self.result_matrix:
            raise TestException("No test results found.")

        # Extended high resistance test has an extra row and an extra column of limit and data.
        self.pass_fail_matrix = Comm2Functions.CreateMatrix(self.num_cols + 1, self.num_rows + 1)
        Comm2Functions.ReportProgress(80)
        Comm2Functions.Trace("Checking result matrix against limits")
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                if self.min_limit_matrix[row][column] <= self.result_matrix[row][column] \
                        <= self.max_limit_matrix[row][column]:
                    # row = rx
                    # column = tx
                    self.pass_fail_matrix[row][column] = 0
                else:
                    self.pass_fail_matrix[row][column] = 1
                    self.failed_points.append((str(column), str(row)))

        for ii in range(0, self.num_rows):
            if self.min_limit_matrix[ii][self.num_cols] <= self.result_matrix[ii][self.num_cols] \
                    <= self.max_limit_matrix[ii][self.num_cols]:
                self.pass_fail_matrix[ii][self.num_cols] = 0

            else:
                self.pass_fail_matrix[ii][self.num_cols] = 1
                self.failed_points.append((str(self.num_cols), str(ii)))

        for jj in range(0, self.num_cols):
            if self.min_limit_matrix[self.num_rows][jj] <= self.Result[self.num_rows][jj] \
                    <= self.max_limit_matrix[self.num_rows][jj]:
                self.pass_fail_matrix[self.num_rows][jj] = 0
            else:
                self.pass_fail_matrix[self.num_rows][jj] = 1
                self.failed_points.append((str(jj), str(self.num_rows)))

        if self.failed_points:
            string_points = []
            for pnt in self.failed_points:
                col_pin = pnt[0]
                row_pin = pnt[1]
                string_points.append("C{0}R{1}".format(col_pin, row_pin))
            self.message = "Failed at: "
            self.message += ", ".join(string_points)

    def set_TRX_MAX(self):
        self.TRX_MAX = self.num_rows if (self.num_rows > self.num_cols) else self.num_cols

    def run(self):
        """
        Actually runs the Extended High Resistance test
        :return:
        """
        self.get_static_config_info()
        self.get_input_params(True)
        self.set_TRX_MAX()

        # col = tx, row = rx
        Comm2Functions.Trace("Creating result matrix...")
        # Extended high resistance test has an extra row and an extra column of limit and data.
        self.result_matrix = Comm2Functions.CreateMatrix(self.num_cols + 1, self.num_rows + 1)

        self.Delta = self.lib.allocate2DArray(self.TRX_MAX, self.TRX_MAX)
        self.Baseline = self.lib.allocate2DArray(self.TRX_MAX, self.TRX_MAX)
        self.Result = self.lib.allocate2DArray(self.TRX_MAX + 1, self.TRX_MAX + 1)

        self.send_get_report()

        # test data in bytes
        data = self.packet.GetPayloadData()
        converted_array = self.convert_report_data(data, True)

        idx = 0
        for ii in range(0, self.num_rows):
            for jj in range(0, self.num_cols):
                self.Baseline[ii][jj] = converted_array[idx]
                idx += 1
                self.Delta[ii][jj] = self.Baseline[ii][jj] - self.Reference[ii][jj]

        my_d = self.ExtHgResData(self.num_rows, self.num_cols, self.Delta, self.Baseline, self.Reference, self.Result)
        self.lib.fnExtended_High_Resistance(my_d)

        self.set_result_matrix(True)

        Comm2Functions.Trace("Analyzing data...")
        self.analyze_data()

        Comm2Functions.Trace("Cleaning up...")
        self.lib.free2DArray(self.Delta, self.TRX_MAX)
        self.lib.free2DArray(self.Reference, self.num_rows)
        self.lib.free2DArray(self.Baseline, self.TRX_MAX)
        self.lib.free2DArray(self.Result, self.TRX_MAX + 1)

        if not self.message:
            self.result = True

    def get_input_params(self, data_dump):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """
        Comm2Functions.Trace("Checking input params...")
        Comm2Functions.ReportProgress(10)

        Comm2Functions.Trace("Getting limits...")
        lim_dim = Comm2Functions.GetInputDimension("Limits")
        if Comm2Functions.GetInputParam("Limits") is None or lim_dim is None:
            raise TestException("No test limits found.")

        Comm2Functions.Trace("Input limit param dimension: " + str(lim_dim[0]) + "x" + str(lim_dim[1]))
        Comm2Functions.Trace("Creating limit matrix...")
        # Extended high resistance test has an extra row and an extra column of limit and data.
        self.limit_matrix = Comm2Functions.CreateMatrix(self.num_cols + 1, self.num_rows + 1)
        self.min_limit_matrix = Comm2Functions.CreateMatrix(self.num_cols + 1, self.num_rows + 1)
        self.max_limit_matrix = Comm2Functions.CreateMatrix(self.num_cols + 1, self.num_rows + 1)
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                idx = Comm2Functions.GetInputIndex("Limits", [row, column])
                try:
                    raw_data = str(Comm2Functions.GetInputParamEx("Limits", idx)).split(":")
                    min_val = raw_data[0].strip("'").strip("\"")
                    max_val = raw_data[1].strip("'").strip("\"")
                    self.limit_matrix[row][column] = "{0} - {1}".format(min_val, max_val)
                    self.min_limit_matrix[row][column] = float(min_val)
                    self.max_limit_matrix[row][column] = float(max_val)
                except ValueError:
                    raw_data = Comm2Functions.GetInputParamEx("Limits", idx)[2:-1].split(":")
                    min_val = float(raw_data[0])
                    max_val = float(raw_data[1])
                    self.limit_matrix[row][column] = "{0} - {1}".format(min_val, max_val)
                    self.min_limit_matrix[row][column] = min_val
                    self.max_limit_matrix[row][column] = max_val
                    continue

                # try:
                #     stripped_value = str(GetInputParamEx("Limits", idx)).strip().strip("'").strip("\"")
                #     self.limit_matrix[row][column] = float(stripped_value)
                # except ValueError:
                #     stripped_value = str(GetInputParamEx("Limits", idx))[1:].strip().strip("'").strip("\"")
                #     self.limit_matrix[row][column] = float(stripped_value)
                #     continue

        # Fill the last row and last column of the limit_matrix with the last row/column of the
        # input limit data.
        for ii in range(0, self.num_rows):
            idx = Comm2Functions.GetInputIndex("Limits", [ii, lim_dim[1] - 1])
            try:
                raw_data = str(Comm2Functions.GetInputParamEx("Limits", idx)).split(":")
                min_val = raw_data[0].strip("'").strip("\"")
                max_val = raw_data[1].strip("'").strip("\"")
                self.limit_matrix[ii][self.num_cols] = "{0} - {1}".format(min_val, max_val)
                self.min_limit_matrix[ii][self.num_cols] = float(min_val)
                self.max_limit_matrix[ii][self.num_cols] = float(max_val)
            except ValueError:
                raw_data = Comm2Functions.GetInputParamEx("Limits", idx)[2:-1].split(":")
                min_val = float(raw_data[0])
                max_val = float(raw_data[1])
                self.limit_matrix[ii][self.num_cols] = "{0} - {1}".format(min_val, max_val)
                self.min_limit_matrix[ii][self.num_cols] = min_val
                self.max_limit_matrix[ii][self.num_cols] = max_val
                continue

            # stripped_value = str(GetInputParamEx("Limits", idx)).strip().strip("'").strip("\"")
            # self.limit_matrix[ii][self.num_cols] = float(stripped_value)

        for jj in range(0, self.num_cols):
            idx = Comm2Functions.GetInputIndex("Limits", [lim_dim[0] - 1, jj])
            try:
                raw_data = str(Comm2Functions.GetInputParamEx("Limits", idx)).split(":")
                min_val = raw_data[0].strip("'").strip("\"")
                max_val = raw_data[1].strip("'").strip("\"")
                self.limit_matrix[self.num_rows][jj] = "{0} - {1}".format(min_val, max_val)
                self.min_limit_matrix[self.num_rows][jj] = float(min_val)
                self.max_limit_matrix[self.num_rows][jj] = float(max_val)
            except ValueError:
                raw_data = Comm2Functions.GetInputParamEx("Limits", idx)[2:-1].split(":")
                min_val = float(raw_data[0])
                max_val = float(raw_data[1])
                self.limit_matrix[self.num_rows][jj] = "{0} - {1}".format(min_val, max_val)
                self.min_limit_matrix[self.num_rows][jj] = min_val
                self.max_limit_matrix[self.num_rows][jj] = max_val
                continue

            # stripped_value = str(GetInputParamEx("Limits", idx)).strip().strip("'").strip("\"")
            # self.limit_matrix[self.num_rows][jj] = float(stripped_value)

        idx = Comm2Functions.GetInputIndex("Limits", [lim_dim[0] - 1, lim_dim[1] - 1])
        # stripped_value = str(GetInputParamEx("Limits", idx)).strip().strip("'").strip("\"")

        try:
            raw_data = str(Comm2Functions.GetInputParamEx("Limits", idx)).split(":")
            min_val = raw_data[0].strip("'").strip("\"")
            max_val = raw_data[1].strip("'").strip("\"")
            self.limit_matrix[self.num_rows][self.num_cols] = "{0} - {1}".format(min_val, max_val)
            self.min_limit_matrix[self.num_rows][self.num_cols] = float(min_val)
            self.max_limit_matrix[self.num_rows][self.num_cols] = float(max_val)
        except ValueError:
            raw_data = Comm2Functions.GetInputParamEx("Limits", idx)[2:-1].split(":")
            min_val = float(raw_data[0])
            max_val = float(raw_data[1])
            self.limit_matrix[self.num_rows][self.num_cols] = "{0} - {1}".format(min_val, max_val)
            self.min_limit_matrix[self.num_rows][self.num_cols] = min_val
            self.max_limit_matrix[self.num_rows][self.num_cols] = max_val

        # self.limit_matrix[self.num_rows][self.num_cols] = float(stripped_value)

        Comm2Functions.Trace("Getting references...")
        if Comm2Functions.GetInputParam("References") is None:
            raise TestException("No references data found.")
        ref_dim = Comm2Functions.GetInputDimension("References")
        if ref_dim is None:
            raise TestException("Invalid references data found.")

        if ref_dim[0] != self.num_cols * self.num_rows:
            raise TestException("References' data size (" + str(ref_dim[0]) +
                                ") is not (num of row * num of columns) " + str(self.num_cols * self.num_rows) + ".")

        Comm2Functions.Trace("Creating References matrix...")
        self.Reference = self.lib.allocate2DArray(self.num_rows, self.num_cols)
        idx = 0
        for row in range(0, self.num_rows):
            for column in range(0, self.num_cols):
                try:
                    val = Comm2Functions.GetInputParamEx("References", idx)
                    self.Reference[row][column] = float(val)
                    idx += 1
                except ValueError:
                    raise TestException("Reference has invalid data.")

        if data_dump:
            Comm2Functions.Trace("Reference data:")
            for ii in range(0, self.num_rows):
                row_buf = "row " + "%2d" % ii + ": "
                for jj in range(0, self.num_cols):
                    if jj > 0:
                        row_buf = row_buf + ", "
                    row_buf = row_buf + "%.3f" % self.Reference[ii][jj]
                Comm2Functions.Trace(row_buf)

        return True

    def cleanup(self):
        if self.packet is not None:
            Comm2Functions.Comm2DsCore_DestroyPacket(self.packet)
        if self.touch_info_packet is not None:
            Comm2Functions.Comm2DsCore_DestroyPacket(self.touch_info_packet)


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def main():
    Comm2Functions.Trace("Extended High Resistance Test STARTED")
    ex_high_resist = ExtendedHighResistance()

    try:
        ex_high_resist.init()

        xml_generator = XMLTestResultGenerator.XMLTestResultGenerator()
        Comm2Functions.Trace("Running Extended High Resistance test now...")
        ex_high_resist.run()

        Comm2Functions.Trace("Creating custom xml")
        xml_generator.set_row_headers(
            ["{0}".format(element) for element in range(0, int(ex_high_resist.num_rows + 1))])
        xml_generator.set_column_headers(
            ["{0}".format(element) for element in range(0, int(ex_high_resist.num_cols + 1))])
        xml_generator.add_matrix(ex_high_resist.pass_fail_matrix, xml_generator.MATRIX_TYPE_LONG, "testResult")
        xml_generator.add_matrix(ex_high_resist.result_matrix, xml_generator.MATRIX_TYPE_DOUBLE, "rawData")
        xml_generator.add_matrix(ex_high_resist.limit_matrix, xml_generator.MATRIX_TYPE_CSV, "limits")

        Comm2Functions.SetCustomResult(str(xml_generator.get_xml()))
        Comm2Functions.SetStringResult(ex_high_resist.message)
        Comm2Functions.SetTestResult(ex_high_resist.result)

    except TestException as err:
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        # retrieve stack trace if any exception other than TestException is thrown somewhere
        track_back_msg = traceback.format_exc()
        Comm2Functions.Trace(track_back_msg)
        Comm2Functions.SetTestResult(False)
    except Exception as e:
        Comm2Functions.Trace(e)
        Comm2Functions.SetStringResult(e)
        # retrieve stack trace if any exception other than TestException is thrown somewhere
        track_back_msg = traceback.format_exc()
        Comm2Functions.Trace(track_back_msg)
        Comm2Functions.SetTestResult(False)
    finally:
        Comm2Functions.Trace("Extended High Resistance Test FINISHED")
        ex_high_resist.cleanup()
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
