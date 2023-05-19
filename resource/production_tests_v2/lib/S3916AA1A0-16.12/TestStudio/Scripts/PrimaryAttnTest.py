## DO NOT MODIFY
## 390a0e84fd7a7d8e01a7c3e89e8141190850f0ef-1.0.0.1
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Primary Attention Test" description="Check line status for ATTN" bin="54" product="S3916A">
# <parameter name="GPIO Pin" type="int" description="GPIO Pin to test"
#                   isoptional="false"
#                   hint="Specify the GPIO pin to test under.  For MPC04, it is pin 13 or 14." >
#                   <default>13</default>
# </parameter>
# </metadata>
##

import Comm2Functions
import re
from Comm2Functions import *
from time import sleep

class TestException(Exception):
    def __init__(self, message):
        self.message = message


class AttnTest(object):
    def __init__(self):
        self.pin_mask = None
        self.result = None

        self.__packet = Comm2DsCore_CreatePacket()
        self.__id_to_send = 0xd2
        self.__attn_test_id = 0x3e

    def run(self):
        self.__get_input_params()
        Trace("Configuring GPIO pins...")
        Comm2DsCore_GpioConfigure(0, 0, self.pin_mask, 0, self.pin_mask, 0, 0, 0)
        Comm2DsCore_WriteCommandReadResponse("target=0 gpio read", 2048, 2000)

        try:
            all_responses = self.__send_commands()
            first_response = all_responses[0]
            second_response = all_responses[1]
        finally:
            self.__disable_attn_deactivate_attn()

        self.__check_responses(first_response, second_response)

    def check_attn_test_availability(self):
        Trace("Checking if ATTN test is available...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x2A, [self.__attn_test_id], self.__packet) != 0:
            raise TestException("ATTN test is not available")
        return True

    def __send_commands(self):
        self.__enable_attn_activate_attn()
        sleep(1)
        response = Comm2DsCore_WriteCommandReadResponse("target=0 gpio read", 2048, 2000)
        first_response = int(self.readMpcBits(response), 16)
        Trace("first response = {0}".format(first_response))

        self.__enable_attn_deactivate_attn()
        sleep(1)
        response = Comm2DsCore_WriteCommandReadResponse("target=0 gpio read", 2048, 2000)
        second_response = int(self.readMpcBits(response), 16)
        Trace("second response = {0}".format(second_response))
        return [first_response, second_response]

    def __check_responses(self, first_response, second_response):
        # Make sure there is a difference between the two

        if first_response != second_response:
            if first_response == int(self.pin_mask) or second_response == int(self.pin_mask):
                SetTestResult(True)
                self.result = True
                return True
            else:
                SetTestResult(False)
                SetStringResult("Unexpected gpio response from MPC04: Expecting = {0}; Received = {1} and {2}".format(
                    self.pin_mask, first_response, second_response))
                return False

        SetStringResult("No change on attention line.")
        SetTestResult(False)
        return False

    def __enable_attn_activate_attn(self):
        Trace("Enabling ATTN test and activating primary attention line...")
        # 8 bit command code followed by 16 bit payload data
        if Comm2DsCore_ExecuteCommand(0x24, [self.__id_to_send, 0x0C, 0x00], self.__packet) != 0:
            raise TestException("Cannot activate primary attention line.")
        return True

    def __enable_attn_deactivate_attn(self):
        Trace("Enabling ATTN test and deactivating primary attention line...")
        # 8 bit command code followed by 16 bit payload data
        if Comm2DsCore_ExecuteCommand(0x24, [self.__id_to_send, 0x04, 0x00], self.__packet) != 0:
            raise TestException("Cannot activate primary attention line.")
        return True

    def __disable_attn_deactivate_attn(self):
        Trace("Disabling ATTN test and deactivating primary attention line...")
        if Comm2DsCore_ExecuteCommand(0x24, [self.__id_to_send, 0x00, 0x00], self.__packet) != 0:
            raise TestException("Cannot disable and deactivate primary attention line.")
        return True

    def __get_input_params(self):
        Trace("Getting input parameters...")
        gpio_parameter = Comm2Functions.GetInputParam("GPIO Pin")[0]
        if gpio_parameter is None:
            raise TestException("No GPIO pin specified to test.")

        if int(gpio_parameter) is not 13 and int(gpio_parameter) is not 14:
            raise TestException("Invalid GPIO pin specified.  It must be pin 13 or 14.")

        temp = int(gpio_parameter) - 1
        rmask = sum([(1 << b) for b in [temp]])
        self.pin_mask = rmask

    @staticmethod
    def readMpcBits(the_response):
        m = re.match(r'<gpio target="0" input="(\d+)"/>', the_response)
        if m:
            v = m.group(1)
            return v
        else:
            return None


def main():
    try:
        test = AttnTest()
        test.check_attn_test_availability()
        test.run()
    except TestException as test_exp:
        Trace(test_exp.message)
        SetStringResult(test_exp.message)
        SetTestResult(False)
    except Exception as exp:
        Trace(exp.message)
        SetStringResult(exp.message)
        SetTestResult(False)


if __name__ == '__main__':
    main()
