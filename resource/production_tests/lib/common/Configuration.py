## DO NOT MODIFY
## e24a74d96009d372ff6af0606833122823b51eed-1.0.0.7
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Configuration Test"
#   description="Configuration test verifies configuration block CRC and customer configuration ID"
#   bin="2">
#       <parameter name="customerConfigId" type="int[]" description="Customer Configuration ID"
#               isoptional="false" isConfigBlockPart = "true" source="customerConfigId" />
#       <parameter name="solutionCRC"  type="int[]" description="Solution Checksum"
#               isoptional="false" isConfigBlockPart = "true" source="checksum" />
#       <parameter name="CRC offset" type="int[]" description="CRC offset"
#               isoptional="false" isConfigBlockPart="true" source="CRCoffset" />
#       <parameter name="CRC length" type="int[]" description="CRC length"
#               isoptional="false" isConfigBlockPart="true" source="CRClength" />
# </metadata>
##

import Comm2Functions


class TestException(Exception):
    def __init__(self, message):
        self.message = message


def check_input_param(name):
    result = Comm2Functions.GetInputParam(name)
    if result is None:
        Comm2Functions.Trace(name + " is invalid")
        raise TestException(name + " is invalid.")
    return result


def main():
    packet = None
    try:
        is_test_pass = True
        custom_id_match = False
        Comm2Functions.Trace("Starting configuration test...")
        custom_id = check_input_param("customerConfigId")
        sln_crc = check_input_param("solutionCRC")
        crc_offset = check_input_param("CRC offset")
        crc_length = check_input_param("CRC length")

        Comm2Functions.Trace("Creating packet...")
        packet = Comm2Functions.Comm2DsCore.CreatePacket()

        Comm2Functions.Trace("Getting customer config ID from appInfo packet...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x20, [], packet) != 0:
            raise TestException("Cannot get app info from device.")
        custom_id_from_device = Comm2Functions.Comm2DsCore.GetVarRawValues(packet, "appInfoPacket_v2", "customerConfigId")
        app_config_block = Comm2Functions.Comm2DsCore.GetVarValues(packet, "appInfoPacket_v2", "appConfigBlock")[0]

        if custom_id_from_device == custom_id:
            is_test_pass = True
            custom_id_match = True

        index = int(crc_offset[0] / 8)
        count = int(crc_length[0] / 8)

        Comm2Functions.Trace("Going to BL...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x1F, [], packet) != 0:
            raise TestException("Cannot switch to BL mode.")
        Comm2Functions.Trace("Getting bootinfo...")
        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x10, [], packet) != 0:
            raise TestException("Cannot get boot info from device.")
        write_block_size = Comm2Functions.Comm2DsCore_GetVarValues(packet, "bootInfoPacket_v2", "WriteBlockSize")[0]

        start_address = write_block_size * app_config_block

        bytestart = [(start_address >> i & 0xff) for i in (0, 8, 16, 24)]
        bytesize = [((index + count) >> i & 0xff) for i in (0, 8)]

        if Comm2Functions.Comm2DsCore.ExecuteCommand(0x13, bytestart + bytesize, packet) != 0:
            raise TestException("Cannot get flash data from device.")

        temp = packet.GetPayloadData()

        final_result = []
        for x in range(index, index + count):
            final_result.append(temp[x])

        sln_crc_print = ''.join('{:02X} '.format(x) for x in sln_crc)
        final_result_print = ''.join('{:02X} '.format(x) for x in final_result)
        custom_id_print = ''.join('{:02X} '.format(x) for x in custom_id)
        custom_id_from_device_print = ''.join('{:02X} '.format(x) for x in custom_id_from_device)

        if final_result == sln_crc:
            crc_match = True
            is_test_pass &= True
        else:
            crc_match = False
            is_test_pass &= False

        if custom_id_match:
            msg = "Configuration ID: PASS \n"
        else:
            msg = "Configuration ID: FAILED \n"
        if crc_match:
            msg += " CRC: PASS \n"
        else:
            msg += " CRC: FAILED \n"

        msg += "Expected Config ID: " + custom_id_print + "\n"
        msg += "Found Config ID: " + custom_id_from_device_print + "\n"
        msg += "Expected CRC: " + sln_crc_print + "\n"
        msg += "Found CRC: " + final_result_print + "\n"
        Comm2Functions.SetStringResult(msg)
        Comm2Functions.SetTestResult(is_test_pass)

    except TestException as e:
        Comm2Functions.Trace(e.message)
        Comm2Functions.SetStringResult(e.message)
        Comm2Functions.SetTestResult(False)
    except Exception as exp:
        Comm2Functions.Trace(exp.message)
        Comm2Functions.SetStringResult(exp.message)
        Comm2Functions.SetTestResult(False)
    finally:
        Comm2Functions.Trace("Going to App...")
        if packet is not None:
            if Comm2Functions.Comm2DsCore.ExecuteCommand(0x14, [], packet) != 0:
                Comm2Functions.Trace("Going to App failed")
            Comm2Functions.Trace("Going to App success")
            Comm2Functions.Comm2DsCore.DestroyPacket(packet)


if __name__ == '__main__':
    main()
