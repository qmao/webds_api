## DO NOT MODIFY
## c3d3e86a5633c81239a6daf5611cfca0cdea40ae-1.0.0.4
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Reset Test" description="Reset Test" bin="6">
# </metadata>
##

from datetime import datetime
from time import sleep

import sys
import Comm2Functions


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def get_fw_mode(a_packet):
    f_w_mode = Comm2Functions.Comm2DsCore.GetVarValues(a_packet, "identifyPacket_v0", "FirmwareMode")
    if f_w_mode is None or len(f_w_mode) != 1:
        raise TestException("Can't get FW mode")
    return f_w_mode[0]

def poll_one_report_packet(packet, id):
    try:
        Comm2Functions.Trace("Getting identify report...")
        read_packet_ret = -1
        read_packet_ret = Comm2Functions.Comm2DsCore.ReadPacket(packet)
        Comm2Functions.Trace('Read packret ret = {0}'.format(read_packet_ret))
        Comm2Functions.Trace('Packet report type = {0}'.format(packet.ReportType))
        if packet.ReportType == id:
            Comm2Functions.Trace('Got report {0}'.format(id))
            return True
        else:
            return False
    except Exception as exp:
        msg = ""
        if sys.version_info[0] < 3:
            # In Python 2.7
            msg = exp.message
        else:
            # In Python 3
            msg = repr(exp)
        Comm2Functions.Trace(msg)
        Comm2Functions.SetStringResult(msg)
        return False


def reset_test(a_packet):
    Comm2Functions.Comm2DsCore.SetCommAbort(True)
    # isTestPass = True
    Comm2Functions.Comm2DsCore.SetCollectPacketInfo("ResetTest", 0x10, 1)

    # PulseResetPin
    # Timeout 500ms
    # Polarity: Level Low  -  (low - 0; high - 1)
    # Output: Open drain - (push pull - 0; open drain - 1)
    Comm2Functions.Comm2DsCore.ResetUut(1000, 0, 1)

    start = datetime.now()
    count = 0
    Comm2Functions.Trace("Start waiting")
    while (datetime.now() - start).total_seconds() < 1 and count == 0:
        isIdentify = poll_one_report_packet(a_packet, 0x10)
        if isIdentify:
            count+=1
            break
        sleep(0.01)
    Comm2Functions.Trace("Done waiting")

    if count != 1:
        # try to get report count one more time
        sleep(0.1)
        isIdentify = poll_one_report_packet(a_packet, 0x10)
        if isIdentify:
            count+=1
        if count != 1:
            Comm2Functions.SetStringResult("Identify is not detected during reset pin usage")
            return False

    # check if we are in BL and if we are not enter BL
    current_mode = get_fw_mode(a_packet)
    if current_mode != 1:
        Comm2Functions.Trace("Detected mode " + str(current_mode))
        Comm2Functions.Trace("Entering app mode...")
        # enter into app mode
        Comm2Functions.Comm2DsCore.ExecuteCommand(0x14, [], a_packet)
        if get_fw_mode(a_packet) != 1:
            Comm2Functions.SetStringResult("Can't enter into APP mode")
            return False
    return True


def main():
    packet = None
    try:
        packet = Comm2Functions.Comm2DsCore.CreatePacket()
        Comm2Functions.SetTestResult(reset_test(packet))
    except TestException as test_exp:
        Comm2Functions.Trace(test_exp.message)
        Comm2Functions.SetStringResult(test_exp.message)
        Comm2Functions.SetTestResult(False)
    except Exception as exp:
        Comm2Functions.Trace(exp.message)
        Comm2Functions.SetStringResult(exp.message)
        Comm2Functions.SetTestResult(False)
    finally:
        if packet is not None:
            Comm2Functions.Comm2DsCore.DestroyPacket(packet)


if __name__ == '__main__':
    main()


def test_main():
    main()
    assert Comm2Functions.GetTestResult() == True, 'Test failed'