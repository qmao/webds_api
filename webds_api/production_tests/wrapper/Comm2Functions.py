import sys
import json
import pandas as pd
import subprocess


sys.path.append("/usr/local/syna/lib/python")
from touchcomm import TouchComm

PT_ROOT = "/usr/local/syna/lib/python/production_tests/"
PT_RUN = PT_ROOT + "run/"

df = None
tc = None
info = None

commands = {
    "CMD_NONE" : 0x00,
    "CMD_CONTINUE_WRITE" : 0x01,
    "CMD_IDENTIFY" : 0x02,			### payload none
    "CMD_DEBUG" : 0x03,
    "CMD_RESET" : 0x04,
    "CMD_ENABLE_REPORT" : 0x05,
    "CMD_DISABLE_REPORT" : 0x06,
    "CMD_ACK" : 0x07, ### / v2
    "CMD_RETRY" : 0x08, ### / v2
    "CMD_SET_MAX_READ_LENGTH" : 0x09, ### / v2
    "CMD_GET_REPORT" : 0x0A, ### / v2

    ### bootloader command
    "CMD_GET_BOOT_INFO" : 0x10,
    "CMD_FLASH_ERASE" : 0x11,
    "CMD_FLASH_WRITE" : 0x12,
    "CMD_FLASH_READ" : 0x13,
    "CMD_RUN_APPLICATION_FW" : 0x14,
    "CMD_SPI_MASTER_WRITE_THEN_READ" : 0x15,
    "CMD_ENTER_MICRO_BOOTLOADER" : 0X16,
    ### application command
    "CMD_ENTER_BOOTLOADER" : 0x1F,
    "CMD_APPLICATION_INFO" : 0x20,
    "CMD_GET_STATIC_CONFIG" : 0x21,
    "CMD_SET_STATIC_CONFIG" : 0x22,
    "CMD_GET_DYNAMIC_CONFIG" : 0x23,
    "CMD_SET_DYNAMIC_CONFIG" : 0x24,
    "CMD_GET_REPORT_CONFIG" : 0x25,
    "CMD_SET_REPORT_CONFIG" : 0x26,
    "CMD_SEND_EXTENDED_COMMAND" : 0x27,
    "CMD_COMMIT_CONFIG" : 0x28,
    "CMD_DESCRIBE_DYNAMIC_CONFIG" : 0x29,
    "CMD_PRODUCTION_TEST" : 0x2A,
    "CMD_SET_CONFIG_ID" : 0x2B,
    "CMD_TOUCH_INFO" : 0x2E,
    "CMD_GET_DATA_LOCATION" : 0x2F,

    "CMD_HOST_DOWNLOAD" : 0x30,
    "CMD_ENTER_PRODUCTION_TEST_MODE" : 0x31,
    "CMD_GET_FEATURES" : 0x32,
    "CMD_CALIBRATE" : 0x33,
    "CMD_START_APPLICATION_ACQUISITION" : 0x37,
    "CMD_STOP_APPLICATION_ACQUISITION" : 0x38,
    "CMD_SET_GLOBAL_STATIC_CONFIG" : 0x39,

    "CMD_GET_ROMBOOT_INFO" : 0x40,
    "CMD_WRITE_PROGRAM_RAM" : 0x41,
    "CMD_RUN_BOOTLOADER_FIRMWARE" : 0x42,
    "CMD_SPI_MASTER_WRITE_THEN_READ_EXTENDED" : 0x43,
    "CMD_ENTER_IO_BRIDGE_MODE" : 0x44,
    "CMD_ROMBOOT_HOSTDOWNLOAD" : 0x45,
}

status = {
    "TOUCHCOMM_RESPONSE_IDLE" : 0,
    "TOUCHCOMM_RESPONSE_OK" : 1,
    "TOUCHCOMM_RESPONSE_CONTINUE_READ" : 3,
    "TOUCHCOMM_RESPONSE_STATUS_CRC_MISMATCH" : 11,
    "TOUCHCOMM_RESPONSE_RECEIVE_BUFFER_OVERFLOW" : 12,
    "TOUCHCOMM_RESPONSE_PREVIOUS_COMMAND_PENDING" : 13,
    "TOUCHCOMM_RESPONSE_NOT_IMPLEMENTED" : 14,
    "TOUCHCOMM_RESPONSE_ERROR" : 15,
    "TOUCHCOMM_RESPONSE_INVALID" : 255,
    "TOUCHCOMM_REPORT_IDENTIFY" : 16,
    "TOUCHCOMM_REPORT_TOUCH" : 17,
    "TOUCHCOMM_REPORT_ACTIVE_DELTA" : 18,
    "TOUCHCOMM_REPORT_ACTIVE_RAW" : 19,
    "TOUCHCOMM_REPORT_ACTIVE_BASELINE" : 20,
    "TOUCHCOMM_REPORT_DOZE_DELTA" : 21,
    "TOUCHCOMM_REPORT_DOZE_RAW" : 22,
    "TOUCHCOMM_REPORT_DOZE_BASELINE" : 23,
    "TOUCHCOMM_REPORT_LOZE_DELTA" : 24,
    "TOUCHCOMM_REPORT_LOZE_RAW" : 25,
    "TOUCHCOMM_REPORT_LOZE_BASELINE" : 26,
    "TOUCHCOMM_REPORT_SLURPER" : 96,
    "TOUCHCOMM_REPORT_PRINTF" : 130,
    "TOUCHCOMM_REPORT_PRINT_BUFFER" : 131,
    "TOUCHCOMM_REPORT_STATUS_LOG" : 134,
}

import xml.etree.ElementTree as ET
class XmlParser():
    def GetTestLimit(test, name):
        tree = ET.parse(PT_RUN +'./Recipe.xml')
        root = tree.getroot()

        test_root = None
        value = None
        datatype = None
        for element in root.findall('test'):
            for metadata in element.findall('metadata'):
                dataname = metadata.get('name')
                if dataname == test:
                    test_root = element
                    for param in test_root.iter('parameter'):
                        if param.attrib['name'] == name:
                            datatype = param.attrib['type']
                            for default in param.iter('default'):
                                value = default.text
                    break

        if test_root is not None:
            for argument in test_root.iter('arg'):
                if argument.attrib['name'] == name:
                    value = argument.text
                    break
            print(test, name, datatype, value)
            if datatype == 'int':
                return [int(value)]
            if datatype == 'int[]':
                return list(map(int, value.split(",")))
            elif datatype == 'bool':
                return int(value)
            elif datatype == 'double':
                return [float(value)]
            elif datatype == 'string[]':
                return list(value.split(","))
            elif datatype == 'double[]':
                return list(map(float, value.split(",")))
            else:
                return [value]

        return None

class TestInfo():
    _instance = None
    _counter = 0
    _test_name = ""
    _test_result = ""

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("TestsInfo init")

    def setValue(self, varname, new_value):
        value = setattr(self, "_" + varname, new_value)

    def getValue(self, varname):
        value = getattr(self, "_" + varname)
        return value

class Packet(object):
    def __init__(self):
        self.raw = {}
        self.parsed = {}
        self.payload = []

    def GetPayloadData(self):
        return bytearray(self.payload)

class Comm2DsCore(object):
    @staticmethod
    def CreatePacket():
        return Packet()

    @staticmethod
    def DestroyPacket(packet):
        pass

    @staticmethod
    def UpdatePacket(cmd, packet, raw):
        packet.ReportType = raw['status']
        packet.payload = raw["payload"]

        if cmd == commands["CMD_IDENTIFY"] or packet.ReportType == status["TOUCHCOMM_REPORT_IDENTIFY"]:
                packet.parsed["identifyPacket_v0"] = tc._processIdentify(packet.payload)
                packet.parsed["identifyPacket_v0"]["FirmwareBuildId"] = packet.parsed["identifyPacket_v0"]["buildID"]
                del packet.parsed["identifyPacket_v0"]["buildID"]
                packet.parsed["identifyPacket_v0"]["FirmwareMode"] = packet.payload[1]
                del packet.parsed["identifyPacket_v0"]["mode"]
                packet.raw["identifyPacket"] = {}
                packet.raw["identifyPacket"]["PartNumber"] = packet.payload[2:18]
        elif cmd == commands["CMD_GET_BOOT_INFO"]:
            packet.parsed["bootInfoPacket_v2"] = tc.decoder.parseBootInfo(packet.payload)
            packet.parsed["bootInfoPacket_v2"]["WriteBlockSize"] = packet.parsed["bootInfoPacket_v2"]["writeBlockWords"]
        elif cmd == commands["CMD_GET_STATIC_CONFIG"]:
            if not tc.decoder.jsonLoaded():
                tc._loadJSONFile()
            packet.parsed["staticConfiguration"] = tc.decoder.parseStaticConfig(packet.payload)
        elif cmd == commands["CMD_APPLICATION_INFO"]:
            packet.parsed["appInfoPacket_v2"] = tc.decoder.parseAppInfo(packet.payload)
            packet.raw["appInfoPacket_v2"] = {}
            packet.raw["appInfoPacket_v2"]["customerConfigId"] = packet.payload[16:32]
        elif cmd == commands["CMD_GET_DYNAMIC_CONFIG"]:
            if not tc.decoder.jsonLoaded():
                tc._loadJSONFile()
            packet.parsed["dynamicConfiguration"] = tc.decoder.parseDynamicConfig(packet.payload)
        else:
            pass

    @staticmethod
    def ExecuteCommand(cmd, args, packet):
        global tc, info

        if cmd == commands["CMD_ENTER_BOOTLOADER"]:
            tc.enterBootloaderMode()
        elif cmd == commands["CMD_RUN_APPLICATION_FW"]:
            tc.runApplicationFirmware()
        else:
            tc.sendCommand(cmd, args)
            raw = tc.getPacket()
            Comm2DsCore.UpdatePacket(cmd, packet, raw)

            info.setValue("counter", info.getValue("counter") + 1)
        return 0

    @staticmethod
    def GetVarValues(packet, block, key):
        print(packet, block, key)
        if block not in packet.parsed:
            return None
        if key not in packet.parsed[block]:
            return None
        if type(packet.parsed[block][key]) == list:
            return packet.parsed[block][key]
        else:
            return [packet.parsed[block][key]]

    @staticmethod
    def SetVarValue(packet, block, key, value):
        if block not in packet.parsed:
            return -1
        if key not in packet.parsed[block]:
            return -1
        if block == "staticConfiguration":
            packet.parsed["staticConfiguration"][key] = value
            tc.setStaticConfig(packet.parsed["staticConfiguration"])
            Comm2DsCore.ExecuteCommand(commands["CMD_GET_STATIC_CONFIG"], [], packet)
        elif block == "dynamicConfiguration":
            packet.parsed["dynamicConfiguration"][key] = value
            tc.setDynamicConfig(packet.parsed["dynamicConfiguration"])
            Comm2DsCore.ExecuteCommand(commands["CMD_GET_DYNAMIC_CONFIG"], [0xff], packet)

    @staticmethod
    def GetVarRawValues(packet, block, key):
        print("RAW", packet, block, key)
        print(packet.raw)
        if block not in packet.raw:
            return None
        if key not in packet.raw[block]:
            return None
        if type(packet.raw[block][key]) == list:
            return packet.raw[block][key]
        else:
            return [packet.raw[block][key]]

    def __init__(self):
        pass

    def TbcFunction():
        print("[TBC]", sys._getframe().f_back.f_code.co_name)

    def SetInterruptCounter(counter):
        global tc, info
        tc = TouchComm.make(protocols='report_streamer', useAttn=True)
        info.setValue("counter", counter)

    def GetInterruptCounter():
        return info.getValue("counter")

    def SetCollectPacketInfo(param1, param2, param3):
        Comm2DsCore.TbcFunction()

    def ResetUut(param1, param2, param3):
        packet = Packet()
        Comm2DsCore.ExecuteCommand(commands["CMD_SET_CONFIG_ID"], ["01", "02", "03", "04", "01", "02", "03", "04", "01", "02", "03", "04", "01", "02", "03", "04"], packet)
        print(packet.parsed)

        Comm2DsCore.ExecuteCommand(commands["CMD_APPLICATION_INFO"], [], packet)
        print(packet.parsed)
        raw = tc.getPacket()

        ##Comm2DsCore.ExecuteCommand(commands["CMD_RESET"], [], packet)
        ##raw = tc.getPacket()

        protocol = tc.comm.get_interface()
        if protocol == "i2c":
            result = subprocess.run(["sudo", "echo", "2",  ">", "/sys/bus/platform/devices/syna_tcm_i2c.0/sysfs/reset"], capture_output=True, text=True)
        elif protocol == "spi":
            result = subprocess.run(["sudo", "echo", "2",  ">", "/sys/bus/platform/devices/syna_tcm_spi.0/sysfs/reset"], capture_output=True, text=True)
        if result is not None:
            print("result:", result)

        packet = Packet()
        Comm2DsCore.ExecuteCommand(commands["CMD_APPLICATION_INFO"], [], packet)
        print(packet.parsed)

        Comm2DsCore.ExecuteCommand(commands["CMD_RESET"], [], packet)

    def SetCommAbort(param1):
        Comm2DsCore.TbcFunction()

    def ReadPacket(packet):
        raw = tc.getPacket()
        print(raw)
        Comm2DsCore.UpdatePacket([], packet, raw)
        return 0

def Comm2DsCore_GetHelper(helper):
    if helper == "staticConfiguration":
        return True
    return None

def Comm2DsCore_CreatePacket():
    return Comm2DsCore.CreatePacket()

def Comm2DsCore_DestroyPacket(packet):
    return Comm2DsCore.DestroyPacket(packet)

def Comm2DsCore_ExecuteCommand(cmd, args, resp):
    return Comm2DsCore.ExecuteCommand(cmd, args, resp)

def Comm2DsCore_GetVarValues(packet, block, key):
    return Comm2DsCore.GetVarValues(packet, block, key)

def Comm2DsCore_SetVarValue(packet, block, key, value):
    return Comm2DsCore.SetVarValue(packet, block, key, value)

def GetInputParam(key):
    global df

    ### parse from xls file
    if key == "Limits":
        test_name = info.getValue("test_name")
        df = pd.read_excel(PT_RUN + "./limits.xls", sheet_name=test_name, header=None)
        return df

    ### parse from xml file
    limit = XmlParser.GetTestLimit(info.getValue("test_name"), key)
    return limit

def GetInputDimension(key):
    if df is None:
        GetInputParam(key)
    if key == "Limits" and df is not None:
        return df.shape
    if key == "References":
        value = XmlParser.GetTestLimit(info.getValue("test_name"), key)
        return [len(value)]

def GetInputIndex(key, row_col):
    if key == "Limits" and df is not None:
        return row_col

def GetInputParamEx(key, index):
    if key == "Limits" and df is not None:
        return df.iat[index[0], index[1]]
    if key == "References":
        value = XmlParser.GetTestLimit(info.getValue("test_name"), key)
        return value[index]

def CreateMatrix(num_cols, num_rows):
    return [[0 for x in range(num_cols)] for y in range(num_rows)]

def Trace(message):
    print(message)

def ReportProgress(progress):
    print("{}% completed".format(progress))

def SetTestResult(result):
    info.setValue("test_result", result)
    print("Pass" if result else "Fail")

def GetTestResult():
    result = info.getValue("test_result")
    return result

def SetStringResult(result):
    print(result)

def SetCustomResult(result):
    pass

def SetSessionVar(session, var):
    pass

def SendMessageBox(message):
    print("[message]", message)

def SetTestName(name):
    info.setValue("test_name", name)

def Init(test):
    global tc, info
    tc = TouchComm.make('report_streamer')
    info = TestInfo()
    SetTestName(test)
