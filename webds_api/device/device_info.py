import json
import sys

class DeviceInfo():
    def identify_type(tc):
        is_smart_bridge = False
        is_multi = None

        try:
            id = tc.identify()
            print(id)
        except:
            pass

        hasTouchCommStorageChip = tc.function("hasTouchCommStorageChip")

        if id['mode'] is None:
            raise HttpServerError("Identify failed")

        if id['mode'] == 'application':
            if id['partNumber'][0:2] == 'SB':
                return {"is_multi_chip": False, "is_smart_bridge": True, "has_touchcomm_storage": hasTouchCommStorageChip}
            feature = tc.function("getFeatures")
            if feature['separateChip']:
                return {"is_multi_chip": True, "is_smart_bridge": False, "has_touchcomm_storage": hasTouchCommStorageChip}
            else:
                return {"is_multi_chip": False, "is_smart_bridge": False, "has_touchcomm_storage": hasTouchCommStorageChip}

            tc.function("sendCommand", args = [tc.getInstance().TOUCHCOMM_CMD_ENTER_BOOTLOADER_MODE])
            id = tc.identify()

        if id['mode'] == 'tddi_bootloader':
            tc.function("sendCommand" , args = [tc.getInstance().TOUCHCOMM_CMD_ENTER_ROM_BOOTLOADER_MODE])
            id = tc.identify()
            print(id)

        if (id['mode'] == 'tddi_slave_bootloader'):
            return True

        if (id['mode'] == 'rombootloader'):
            try:
                if id['partNumber'][0:2] == 'SB':
                    is_smart_bridge = True
                else:
                    rom_id = tc.function("romIdentify")
                    print(rom_id)
                    info = tc.function("getRomBootInfo")
                    print(info)
                    is_multi = True
            except Exception as e:
                is_multi = False
                pass

        if is_multi is None and not is_smart_bridge:
            raise HttpServerError("Cannot determine device type")

        return {"is_multi_chip": is_multi, "is_smart_bridge": is_smart_bridge, "has_touchcomm_storage": hasTouchCommStorageChip}
