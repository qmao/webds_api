import time
from decimal import *


class LocalDimming(object):

    def __init__(self, tc):
         # SB7900 parameters
        self.debug = False
        self.has_touchcomm_storage = False
        self.is_multi_chip = False
        self.no_bootloader_fw = True
        self.spiMode = 0
        self.resetOnConnect = True
        self.useAttn = True
        self.bare_connection = False
        self.tc = tc

        # for Local Dimming parameters
        self.brightness = 920
        self.darkSceneEnabled = 0
        self.outsideLightLevel = 0

        # for internal-use constans
        self._coef_nit_per_dbv = 0.102290985
        self._outsideLightLevel_dark = 0
        self._outsideLightLevel_bright = 1

        # register-field definitions
        self._base_disp_ctrl = 0x21080000
        self._ofs_st0_dbv = 0x7200
        self._bitofs_st0_dbv = 0
        self._bitlen_st0_dbv = 16
        self._mask_st0_dbv = ((2**self._bitlen_st0_dbv) - 1) << self._bitofs_st0_dbv
        self._ofs_st0_ld_p1 = 0x80D4
        self._bitofs_st0_c1_c0 = 0
        self._bitlen_st0_c1_c0 = 2
        self._mask_st0_c1_c0 = ((2**self._bitlen_st0_c1_c0) - 1) << self._bitofs_st0_c1_c0
        self._ofs_st0_ld_p46 = 0x8188
        self._bitofs_st0_area_calc_ofs = 0
        self._bitlen_st0_area_calc_ofs = 8
        self._mask_st0_area_calc_ofs = ((2**self._bitlen_st0_area_calc_ofs) - 1) << self._bitofs_st0_area_calc_ofs

        # globla constants
        self.LD_PARAM_C__LOCAL_DIMMING_OFF = 0x0
        self.LD_PARAM_C__LOCAL_DIMMING_ON = 0x3
        self.LD_PARAM_AREA_CALC_OFS__OFF = 0x80
        self.LD_PARAM_AREA_CALC_OFS__DARK_MODE = 0x6E
        self.LD_PARAM_AREA_CALC_OFS__BRIGHT_MODE = 0x60

    def powerOn(self):
        print("Power On Sequence")
        id = self.tc.identify()
        print(id)

        if id['mode'] == 'rombootloader':
            self.tc.runApplicationFirmware()
            id = self.tc.identify()
            print(id)

        if id['mode'] == 'application':
            self.GetOutsideLightLevel()
            self.GetBrightness()

        print("Power On Sequence Complete")

    def getField(self, reg_addr, field_mask, field_ofs) -> int:
        ret = self.tc.readRegister(reg_addr)
        return (ret & field_mask) >> field_ofs

    def setField(self, reg_addr, field_mask, field_ofs, val) -> None:
        ret = self.tc.readRegister(reg_addr)
        reg_val = (ret & ~field_mask) | ((val << field_ofs) & field_mask)
        # FIXME: put delay between TCM v2 command makes stable operation...
        time.sleep(0.001)
        self.tc.writeRegister(reg_addr, reg_val)

    def getDbv(self) -> int:
        reg_addr = self._base_disp_ctrl + self._ofs_st0_dbv
        field_mask = self._mask_st0_dbv
        field_ofs = self._bitofs_st0_dbv

        return self.getField(reg_addr, field_mask, field_ofs)

    def setDbv(self, val:int) -> int:
        reg_addr = self._base_disp_ctrl + self._ofs_st0_dbv
        field_mask = self._mask_st0_dbv
        field_ofs = self._bitofs_st0_dbv

        self.setField(reg_addr, field_mask, field_ofs, val)
        # FIXME: put delay between TCM v2 command makes stable operation...
        time.sleep(0.001)
        return self.getDbv()

    def getLdAreaCalcOfs(self) -> int:
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p46
        field_mask = self._mask_st0_area_calc_ofs
        field_ofs = self._bitofs_st0_area_calc_ofs

        return self.getField(reg_addr, field_mask, field_ofs)

    def setLdAreaCalcOfs(self, val:int) -> int:
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p46
        field_mask = self._mask_st0_area_calc_ofs
        field_ofs = self._bitofs_st0_area_calc_ofs

        self.setField(reg_addr, field_mask, field_ofs, val)
        # FIXME: put delay between TCM v2 command makes stable operation...
        time.sleep(0.001)
        return self.getLdAreaCalcOfs()

    def EnableLocalDimming(self, enable : bool):
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p1
        field_ofs = self._bitofs_st0_c1_c0
        field_mask = self._mask_st0_c1_c0
        if enable:
            val = self.LD_PARAM_C__LOCAL_DIMMING_ON
        else:
            val = self.LD_PARAM_C__LOCAL_DIMMING_OFF

        self.setField(reg_addr, field_mask, field_ofs, val)

    def EnableDarkSceneEnhancement(self, enable : bool):
        self.darkSceneEnabled = enable
        self.SetOutsideLightLevel(self.outsideLightLevel)

    def SetOutsideLightLevel(self, level : int):
        self.outsideLightLevel = level
        val = self.LD_PARAM_AREA_CALC_OFS__OFF
        if (self.darkSceneEnabled):
            if (self.outsideLightLevel == self._outsideLightLevel_dark):
                val = self.LD_PARAM_AREA_CALC_OFS__DARK_MODE
            elif  (self.outsideLightLevel == self._outsideLightLevel_bright):
                val = self.LD_PARAM_AREA_CALC_OFS__BRIGHT_MODE

        self.setLdAreaCalcOfs(val)

    def GetOutsideLightLevel(self) -> int:
        val = self.getLdAreaCalcOfs()
        if (val == self.LD_PARAM_AREA_CALC_OFS__OFF):
            pass # to keep last value
        elif (val == self.LD_PARAM_AREA_CALC_OFS__DARK_MODE):
            self.outsideLightLevel = self._outsideLightLevel_dark
        elif (val == self.LD_PARAM_AREA_CALC_OFS__BRIGHT_MODE):
            self.outsideLightLevel = self._outsideLightLevel_bright

        return self.outsideLightLevel

    def SetBrightness(self, brightness : int):
        # README: python's round() is not a populer round up/down function
        # https://docs.python.org/ja/3/library/functions.html#round
        dbv = round(brightness / self._coef_nit_per_dbv)
        self.brightness = self._coef_nit_per_dbv * self.setDbv(dbv)

    def GetBrightness(self) -> int:
        self.brightness = self._coef_nit_per_dbv * self.getDbv()
        return self.brightness

if __name__ == "__main__":
    pass