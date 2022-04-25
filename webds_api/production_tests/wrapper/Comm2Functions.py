import sys
import json
import pandas as pd


sys.path.append("/usr/local/syna/lib/python")
from touchcomm import TouchComm

PT_ROOT = "/usr/local/syna/lib/python/production_tests/"
PT_RUN = PT_ROOT + "run/"

df = None
tc = None
info = None

import xml.etree.ElementTree as ET
class XmlParser():
    def GetTestLimit(test, name):
        tree = ET.parse(PT_RUN +'./Recipe.xml')
        root = tree.getroot()

        command_root = None
        for command in root.findall('command'):
            for metadata in command.findall('metadata'):
                dataname = metadata.get('name')
                if dataname == test:
                    command_root = command
                    break

        if command_root is not None:
            for argument in command_root.iter('arg'):
                print(argument.attrib)
                if argument.attrib['name'] == name:
                    if argument.attrib['type'] == 'int':
                        return [int(argument.text)]
                    elif argument.attrib['type'] == 'bool':
                        return int(argument.text)
                    else:
                        return [argument.text]
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
    def ExecuteCommand(cmd, args, packet):
        tc.sendCommand(cmd, args)
        packet.payload = tc.getResponse()
        if cmd == 0x02:
            packet.parsed["identifyPacket_v0"] = tc._processIdentify(packet.payload)
            packet.parsed["identifyPacket_v0"]["FirmwareBuildId"] = packet.parsed["identifyPacket_v0"]["buildID"]
            del packet.parsed["identifyPacket_v0"]["buildID"]
            packet.parsed["identifyPacket_v0"]["FirmwareMode"] = packet.payload[1]
            del packet.parsed["identifyPacket_v0"]["mode"]
            packet.raw["identifyPacket"] = {}
            packet.raw["identifyPacket"]["PartNumber"] = packet.payload[2:18]
        elif cmd == 0x21:
            if not tc.decoder.jsonLoaded():
                tc._loadJSONFile()
            packet.parsed["staticConfiguration"] = tc.decoder.parseStaticConfig(packet.payload)
        elif cmd == 0x23:
            if not tc.decoder.jsonLoaded():
                tc._loadJSONFile()
            packet.parsed["dynamicConfiguration"] = tc.decoder.parseDynamicConfig(packet.payload)
        else:
            pass
        return 0

    @staticmethod
    def GetVarValues(packet, block, key):
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
            Comm2DsCore.ExecuteCommand(0x21, [], packet)
        elif block == "dynamicConfiguration":
            packet.parsed["dynamicConfiguration"][key] = value
            tc.setDynamicConfig(packet.parsed["dynamicConfiguration"])
            Comm2DsCore.ExecuteCommand(0x23, [0xff], packet)

    @staticmethod
    def GetVarRawValues(packet, block, key):
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
        info.setValue("counter", counter)
        Comm2DsCore.TbcFunction()

    def GetInterruptCounter():
        Comm2DsCore.TbcFunction()
        return info.getValue("counter")

    def SetCollectPacketInfo(param1, param2, param3):
        Comm2DsCore.TbcFunction()

    def ResetUut(param1, param2, param3):
        Comm2DsCore.TbcFunction()

    def SetCommAbort(param1):
        Comm2DsCore.TbcFunction()

    def ReadPacket(param1):
        Comm2DsCore.TbcFunction()
        packet = { ReportType: 0 }
        return packet

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
    if key == "Limits" and df is not None:
        return df.shape

def GetInputIndex(key, row_col):
    if key == "Limits" and df is not None:
        return row_col

def GetInputParamEx(key, index):
    if key == "Limits" and df is not None:
        return df.iat[index[0], index[1]]

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

def SetTestName(name):
    info.setValue("test_name", name)

def Init(test):
    global tc, info
    tc = TouchComm.make('report_streamer')
    info = TestInfo()
    SetTestName(test)
