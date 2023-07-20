import sys
import tornado
sys.path.append("/usr/local/syna/lib/python")
from programmer import AsicProgrammer
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError
from ..device.device_info import DeviceInfo

class ProgrammerManager(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ProgrammerManager singleton object is created")

    def program(filename):
        ### disconnect tcm if exist
        is_tddi = False
        is_multi_chip = False
        is_smart_bridge = False

        if ".ihex" in filename:
            is_tddi = True
            device_info = DeviceInfo.identify_type(TouchcommManager())
            print(device_info)
            is_multi_chip = device_info["is_multi_chip"]
            is_smart_bridge = device_info["is_smart_bridge"]
            has_touchcomm_storage = device_info["has_touchcomm_storage"]

        try:
            tc = TouchcommManager()
            tc.disconnect()
        except:
            print("tcm not exist")
            pass

        tc.lock(True)
        try:
            if is_smart_bridge:
                print("[SB] program iHex File")
                AsicProgrammer.programIHexFile(filename, resetOnConnect=True, is_multi_chip=False, has_touchcomm_storage=False, no_bootloader_fw=True)

            elif is_tddi:
                print("program iHex File")
                AsicProgrammer.programIHexFile(filename, is_multi_chip=is_multi_chip, has_touchcomm_storage=has_touchcomm_storage)

            else:
                print("program Hex File")
                AsicProgrammer.programHexFile(filename, communication='socket', server='127.0.0.1')
        finally:
            tc.lock(False)