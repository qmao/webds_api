import sys
import tornado
sys.path.append("/usr/local/syna/lib/python")
from programmer import AsicProgrammer
from ..touchcomm.touchcomm_manager import TouchcommManager

class ProgrammerManager(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ProgrammerManager singleton object is created")

    def identify_device():
        is_smart_bridge = False
        is_multi = None

        tc = TouchcommManager()

        try:
            id = tc.identify()
            print(id)
        except:
            pass

        if id['mode'] is None:
            message = "Identify failed"
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        if id['mode'] == 'application':
            if id['partNumber'][0:2] == 'SB':
                return {"is_multi": False, "is_smart_bridge": True}
            feature = tc.getInstance().getFeatures()
            if feature['separateChip']:
                return {"is_multi": True, "is_smart_bridge": False}
            else:
                return {"is_multi": False, "is_smart_bridge": False}

            tc.getInstance().sendCommand(tc.getInstance().TOUCHCOMM_CMD_ENTER_BOOTLOADER_MODE)
            id = tc.identify()
            print(id)

        if id['mode'] == 'tddi_bootloader':
            tc.getInstance().sendCommand(tc.getInstance().TOUCHCOMM_CMD_ENTER_ROM_BOOTLOADER_MODE)
            id = tc.identify()
            print(id)

        if (id['mode'] == 'tddi_slave_bootloader'):
            return True
            ##tc.getInstance().sendCommand(tc.getInstance().TOUCHCOMM_CMD_ENTER_ROM_BOOTLOADER_MODE)
            ##id = tc.identify()
            ##print(id)

        if (id['mode'] == 'rombootloader'):
            try:
                if id['partNumber'][0:2] == 'SB':
                    is_smart_bridge = True
                else:
                    rom_id = tc.getInstance().romIdentify()
                    print(rom_id)
                    info = tc.getInstance().getRomBootInfo()
                    print(info)
                    is_multi = True
            except Exception as e:
                is_multi = False
                pass

        if is_multi is None and not is_smart_bridge:
            message = "Cannot determine device type"
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        return {"is_multi": is_multi, "is_smart_bridge": is_smart_bridge}

    def program(filename):
        ### disconnect tcm if exist
        is_tddi = False
        is_multi_chip = False
        is_smart_bridge = False

        if ".ihex" in filename:
            is_tddi = True
            device_info = ProgrammerManager.identify_device()
            print(device_info)
            is_multi_chip = device_info["is_multi"]
            is_smart_bridge = device_info["is_smart_bridge"]

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
                AsicProgrammer.programIHexFile(filename, is_multi_chip=is_multi_chip)

            else:
                print("program Hex File")
                AsicProgrammer.programHexFile(filename, communication='socket', server='127.0.0.1')
        finally:
            tc.lock(False)