## DO NOT MODIFY
## 2a393d5df55ad5646f281175318e7f48319290ce-1.0.0.6
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Firmware ID Test" description="Firmware ID Test verifies firmware number" bin="20">
#   <parameter name="Firmware ID" type="int[]" description="Firmware ID to compare against one found on device."
#               isoptional="false" isConfigBlockPart="true" source="buildID"/>
# </metadata>
##

import Comm2Functions


class FirmwareIDTest(object):
    def __init__(self):
        self.build_id_from_device = 0
        self.build_id_to_compare = 0
        self.result = False
        self.message = ""

    def get_fw_id_from_device(self):
        identify_packet = None
        try:
            identify_packet = Comm2Functions.Comm2DsCore.CreatePacket()
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x02, [], identify_packet) != 0:
                raise TestException("Cannot obtain identify packet from device.")
            identify_device = Comm2Functions.Comm2DsCore.GetVarValues(identify_packet, "identifyPacket_v0", "FirmwareBuildId")
            if identify_device is None or len(identify_device) != 1:
                raise TestException("Failed to get firmware ID from device.")
            return identify_device[0]
        finally:
            if identify_packet is not None:
                Comm2Functions.Comm2DsCore.DestroyPacket(identify_packet)

    def get_input_params(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """

        build_id = Comm2Functions.GetInputParam("Firmware ID")
        if build_id is None:
            raise TestException("No firmware ID given to compare against.  Please check input parameters.")
        identify_param = 0
        for x in range(0, len(build_id)):
            identify_param |= (build_id[x] << (8 * x))
        return identify_param

    def run(self):
        Comm2Functions.Trace("Getting build ID to compare against...")
        self.build_id_to_compare = self.get_input_params()
        
        Comm2Functions.Trace("Getting identify packet...")
        self.build_id_from_device = self.get_fw_id_from_device()
        Comm2Functions.Trace("Build from device: " + str(self.build_id_from_device))   # dec format
        Comm2Functions.SetSessionVar("FW_ID", str(self.build_id_from_device))
        
        self.result = self.build_id_to_compare == self.build_id_from_device
        self.message += "Firmware ID found on device: " + str(self.build_id_from_device)
        self.message += "\n"
        self.message += "Firmware ID to compare: " + str(self.build_id_to_compare)


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def main():
    Comm2Functions.Trace("Firmware ID Test STARTED")
    fw_id_test = FirmwareIDTest()

    try:
        Comm2Functions.Trace("Checking input params")
        Comm2Functions.ReportProgress(10)
        if fw_id_test.get_input_params() == 0:
            raise TestException("Invalid input parameters")

        Comm2Functions.Trace("Running firmware ID test now...")
        Comm2Functions.ReportProgress(50)
        fw_id_test.run()

        Comm2Functions.SetStringResult(fw_id_test.message)
        Comm2Functions.SetTestResult(fw_id_test.result)

    except TestException as err:
        Comm2Functions.Trace(err.message)
        Comm2Functions.SetStringResult(err.message)
        Comm2Functions.SetTestResult(False)
    except Exception as exp:
        Comm2Functions.Trace(exp.message)
        Comm2Functions.SetStringResult(exp.message)
        Comm2Functions.SetTestResult(False)
    finally:
        Comm2Functions.Trace("Firmware ID Test FINISHED")
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()


def test_main():
    main()
    assert Comm2Functions.GetTestResult() == True, 'Test failed'