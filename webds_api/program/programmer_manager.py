import sys
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

    def isMultiChip():
        isMulti = None

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
            feature = tc.getInstance().getFeatures()
            if feature['separateChip']:
                return True
            else:
                return False

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
                id = tc.getInstance().romIdentify()
                print(id)
                info = tc.getInstance().getRomBootInfo()
                print(info)
                isMulti = True
            except Exception as e:
                isMulti = False
                pass

        if isMulti is None:
            message = "Cannot determin TDDI type"
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        return isMulti

    def program(filename):
        ### disconnect tcm if exist
        isTddi = False
        is_multi_chip = False

        if ".ihex" in filename:
            isTddi = True
            is_multi_chip = ProgrammerManager.isMultiChip()
            print("Multi Chip: {}".format(is_multi_chip))

        try:
            tc = TouchcommManager()
            tc.disconnect()
        except:
            print("tcm not exist")
            pass

        tc.lock(True)
        try:
            if isTddi:
                print("program IHex File")
                AsicProgrammer.programIHexFile(filename, is_multi_chip=is_multi_chip)
            else:
                print("program Hex File")
                AsicProgrammer.programHexFile(filename, communication='socket', server='127.0.0.1')
        finally:
            tc.lock(False)