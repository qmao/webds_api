## DO NOT MODIFY
## 66b7c10a2abd331afd43196c8a22179adec3a22f-1.0.0.7
## DO NOT MODIFY
## Metadata:
# <?xml version="1.0" encoding="utf-8"?>
# <metadata name="Device Package Test" description="Device Package Test verifies part number" bin="19" product="S3916A">
#   <parameter name="Device Package" type="string" description="Device package to compare against the one found on device."
#               isoptional="false" isSolutionFile="false" sourceFileType=""/>
# </metadata>
##

import Comm2Functions
import traceback


class TestException(Exception):
    def __init__(self, message):
        self.message = message


class DevicePackageTest(object):
    def __init__(self):
        self.device_package_from_device = None
        self.device_package_to_compare = None
        self.result = False
        self.message = ''

    def get_device_package_from_device(self):
        identify_packet = None
        try:
            Comm2Functions.Trace('Getting identify packet...')
            identify_packet = Comm2Functions.Comm2DsCore_CreatePacket()
            if Comm2Functions.Comm2DsCore_ExecuteCommand(0x02, [], identify_packet) != 0:
                raise TestException('Cannot obtain identify packet from device.')
            else:
                temp_raw = Comm2Functions.Comm2DsCore.GetVarRawValues(identify_packet, 'identifyPacket', 'PartNumber')
                if temp_raw is None:
                    raise TestException('Failed to get part number raw data from identify packet.')
                temp_str = ''

                if chr(temp_raw[10]) == ':':  # part number containing ":" has mixed format: string & integer parts
                    part_string_list = temp_raw[:10]
                    version_list = temp_raw[11:]
                    part_string = temp_str.join(chr(c) for c in filter(lambda a: a != 0, part_string_list))
                    version_string = ''
                    for c in version_list:
                        if c != 0:
                            if version_string != '':
                                version_string += '.'  # add '.' after the number string
                            version_string += str(c)

                    part_number_str = part_string + ':' + version_string
                else:
                    part_number_str = temp_str.join(chr(c) for c in filter(lambda a: a != 0, temp_raw))

                self.device_package_from_device = part_number_str
        finally:
            if identify_packet is not None:
                Comm2Functions.Comm2DsCore.DestroyPacket(identify_packet)

    def get_input_params(self):
        """
        Verifies input parameters specified in metadata
        :return: boolean - True if all required inputs are valid
        """
        ret = True
        try:
            Comm2Functions.Trace('Getting build ID to compare against...')
            device_package = Comm2Functions.GetInputParam('Device Package')
            if device_package is None:
                ret = False
                raise TestException('No Device Package found.')
            if len(device_package) != 1:
                ret = False
                raise TestException('Device Package string length = {0}'.format(len(device_package)))

            self.device_package_to_compare = device_package[0]
            if self.device_package_to_compare is None:
                ret = False
                Comm2Functions.Trace('Invalid Device Package to compare against.')
            if self.device_package_to_compare == '':
                ret = False
                Comm2Functions.Trace('Device Package string to compare against is empty.')
            # trim off the double quote char from input string
            if self.device_package_to_compare[0] == '"':
                self.device_package_to_compare = self.device_package_to_compare[1:]
            if self.device_package_to_compare[-1] == '"':
                self.device_package_to_compare = self.device_package_to_compare[:-1]

        finally:
            Comm2Functions.Trace('Target parameter = {0}'.format(self.device_package_to_compare))
            return ret

    def run(self):
        self.get_input_params()
        self.get_device_package_from_device()
        Comm2Functions.ReportProgress(50)
        self.result = self.device_package_to_compare == self.device_package_from_device

        self.message = 'Package string found on device: ' + str(
            self.device_package_from_device) + '; Package string to compare: ' + str(self.device_package_to_compare)


def main():
    track_back_msg = None
    Comm2Functions.Trace('Device Package Test STARTED')
    package_test = DevicePackageTest()

    try:
        Comm2Functions.Trace('Checking input params')
        Comm2Functions.ReportProgress(10)
        if not package_test.get_input_params():
            raise TestException('Invalid input parameters')

        Comm2Functions.Trace('Running Device Package test now...')
        package_test.run()

        Comm2Functions.SetStringResult(package_test.message)
        Comm2Functions.SetTestResult(package_test.result)

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
        Comm2Functions.Trace('Device Package Test FINISHED')
        Comm2Functions.ReportProgress(100)


if __name__ == '__main__':
    main()
