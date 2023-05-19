## DO NOT MODIFY
## 8a7f9c84117bab356557a7355f898ee4c42cb088-1.0.0.3
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata 
#        name="Attention Test"
#        description="Attention test description"
#        bin="1">
# </metadata>
##

from time import sleep

import Comm2Functions


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def exec_command(a_packet):
    if Comm2Functions.Comm2DsCore.ExecuteCommand(0x02, [], a_packet) != 0:
        raise TestException("Cannot get app info")


def main():
    packet = None
    is_interrupt_happen = None
    try:
        is_interrupt_happen = False
        packet = Comm2Functions.Comm2DsCore.CreatePacket()
        Comm2Functions.Trace("Setting int counter to 0")
        counter = 0
        Comm2Functions.Comm2DsCore.SetInterruptCounter(counter)
        exec_command(packet)
        sleep(0.2)
        counter = Comm2Functions.Comm2DsCore.GetInterruptCounter()
        Comm2Functions.Trace(str(counter))
        is_interrupt_happen = (counter > 0)
        Comm2Functions.SetTestResult(is_interrupt_happen)
    except TestException as e:
        Comm2Functions.Trace(e.message)
        Comm2Functions.SetStringResult(e.message)
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
