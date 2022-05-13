## DO NOT MODIFY
## e2d6a1e74b496891e90e1ecf3869e5730c272329-1.0.0.3
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Lockdown" description="Reads and checks integrity of lockdown settings." bin="57" product="S3908">
#   <parameter name="Lockdown settings" type="string" description="Lockdown settings to compare against one
#   found on device." isoptional="false" isSolutionFile="true" sourceFileType="ds6bcLockdown" />
# </metadata>
##

import Comm2Functions


class LockdownTest(object):

    def __init__(self):
        self.WORD_SIZE = 4
        self.packet = Comm2Functions.Comm2DsCore.CreatePacket()
        self.message = ""
        self.result = False
        self.appendedString = ""
        self.customer_otp_start_block = None
        self.customer_otp_blocks = None
        self.write_block_size = None
        self.customer_otp_from_soln = None
        self.customer_otp_from_device = None
        self.serial_num = ""
        self.detected_fw_mode = None

    @staticmethod
    def reset():
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
            if packet is not None:
                Comm2Functions.Comm2DsCore.DestroyPacket(packet)

    @staticmethod
    def is_protocol_slot(block):
        return block[1] >> 7 == 1

    def custom_range_reverse(self, byte_array):
        start = len(byte_array) - 1
        while start > 0:
            ret_val = []
            for x in range(2 * self.WORD_SIZE - 1, -1, -1):
                ret_val.append(byte_array[start - x])
            yield ret_val
            start -= 2 * self.WORD_SIZE

    def __check_fw_mode(self):
        Comm2Functions.Trace("Identifying...")
        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x02, [], self.packet) != 0:
            raise TestException("Cannot identify firmware.")

        fw_mode_helper = Comm2Functions.Comm2DsCore_GetVarValues(self.packet, "identifyPacket_v0", "FirmwareMode")

        if fw_mode_helper is not None:
            self.detected_fw_mode = fw_mode_helper[0]

        if self.detected_fw_mode is None:
            raise TestException("Unknown firmware mode; cannot read customer OTP block.")

    def __get_into_bl_mode(self):
        Comm2Functions.Trace("Entering into bootloader mode...")
        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x1F, [], self.packet) != 0:
            raise TestException("Cannot enter into bootloader mode.")

    def __get_boot_info(self):
        Comm2Functions.Trace("Getting boot info...")
        if Comm2Functions.Comm2DsCore_ExecuteCommand(0x10, [], self.packet) != 0:
            raise TestException("Cannot obtain boot information.")

        if self.detected_fw_mode == 4 or self.detected_fw_mode == 12 or self.detected_fw_mode == 13:
            # TDDI BL
            raw_otp_start_block = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "CustomerOtpStartBlock")
            if raw_otp_start_block is None:
                raise TestException("Cannot find CustomerOtpStartBlock from bootloader.")

            raw_otp_block = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "CustomerOtpBlocks")
            if raw_otp_block is None:
                raise TestException("Cannot find CustomerOtpBlocks from bootloader.")

            raw_write_block_size = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "WriteBlockSize")
            if raw_write_block_size is None:
                raise TestException("Cannot find WriteBlockSize from bootloader.")
        elif self.detected_fw_mode == 11:
            # Discrete BL
            raw_otp_start_block = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "BootConfigStartBlock")
            if raw_otp_start_block is None:
                raise TestException("Cannot find BootConfigStartBlock from bootloader.")

            raw_otp_block = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "BootConfigSize")
            if raw_otp_block is None:
                raise TestException("Cannot find BootConfigSize from bootloader.")

            raw_write_block_size = Comm2Functions.Comm2DsCore.GetVarValues(self.packet, "bootInfoPacket", "WriteBlockSize")
            if raw_write_block_size is None:
                raise TestException("Cannot find WriteBlockSize from bootloader.")
        else:
            raise TestException("Unrecognised firmware mode; cannot read customer OTP block.")

        self.customer_otp_start_block = raw_otp_start_block[0]
        self.customer_otp_blocks = raw_otp_block[0]
        self.write_block_size = raw_write_block_size[0]

    def __read_customer_otp(self):
        customer_otp_start = self.customer_otp_start_block * self.write_block_size
        size = self.write_block_size * self.customer_otp_blocks

        byte_start = [(customer_otp_start >> i & 0xff) for i in (0, 8, 16, 24)]

        byte_size = [(size >> i & 0xff) for i in (0, 8)]

        Comm2Functions.Trace("Reading customer otp...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x13, byte_start + byte_size, self.packet) != 0:
            raise TestException("Cannot get customer otp from device.")

        self.customer_otp_from_device = self.packet.GetPayloadData()

    def __get_serial_num_string(self):
        pca_in_string = ""
        for char in self.customer_otp_from_device:
            if char in range(0, 31) or char == 255:
                pca_in_string += " "
                continue
            else:
                pca_in_string += str(chr(char))
        return pca_in_string

    def __get_lockdown_area(self, customer_otp):
        if customer_otp is None:
            return None

        # first one is the latest since we are reading backwards
        for x in self.custom_range_reverse(customer_otp):
            if self.is_protocol_slot(x):
                return x

    def __get_lockdown_from_soln(self):
        result = Comm2Functions.GetInputParam("Lockdown settings")
        if result is None:
            raise TestException("Lockdown settings from solution is invalid.")
        self.customer_otp_from_soln = [int(x) for x in str(result[0]).strip().split(',')]

    def run(self):
        self.__get_lockdown_from_soln()
        self.__get_into_bl_mode()
        self.__check_fw_mode()
        self.__get_boot_info()
        self.__read_customer_otp()
        self.result = self.__do_comparison()
        return True

    def __do_comparison(self):
        lockdown_area_soln = self.__get_lockdown_area(self.customer_otp_from_soln)
        lockdown_area_device = self.__get_lockdown_area(self.customer_otp_from_device)
        self.message = "Lockdown area in solution = {0}; Lockdown area on device = {1}".format(
            [hex(x) for x in lockdown_area_soln], [hex(y) for y in lockdown_area_device])
        return lockdown_area_soln == lockdown_area_device

    def cleanup(self):
        if self.packet is not None:
            Comm2Functions.Comm2DsCore_DestroyPacket(self.packet)
        Comm2Functions.Trace("Resetting device...")
        LockdownTest.reset()


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def main():
    Comm2Functions.Trace("Lockdown Test STARTED")
    lockdown_test = LockdownTest()

    try:
        Comm2Functions.Trace("Running lockdown test now...")
        lockdown_test.run()
        Comm2Functions.SetStringResult(lockdown_test.message)
        Comm2Functions.SetTestResult(lockdown_test.result)
    except TestException as err:
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        Comm2Functions.SetTestResult(False)
    except Exception as e:
        Comm2Functions.Trace(e)
        Comm2Functions.SetStringResult(e)
        Comm2Functions.SetTestResult(False)
    finally:
        Comm2Functions.Trace("Lockdown Test FINISHED")
        lockdown_test.cleanup()
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
