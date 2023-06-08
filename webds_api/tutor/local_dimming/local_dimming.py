import time
from typing import Union
from decimal import *
from smbus2 import SMBus, i2c_msg


class LocalDimming(object):

    def __init__(self, tc):
        # SB7900 parameters
        self.debug = False
        self.has_touchcomm_storage = False
        self.is_multi_chip = False
        self.no_bootloader_fw = True
        self.spiMode = 0
        self.resetOnConnect = False
        self.useAttn = False
        self.bare_connection = True
        self.tc = tc
        self.isAppMode = False

        # for Local Dimming parameters
        self.brightness = 920
        self.darkSceneEnabled = 0
        self.outsideLightLevel = 0
        self.isCoeffRamLoaded = False

        # for internal-use constans
        self._coef_nit_per_dbv = 0.102290985
        self._outsideLightLevel_dark = 0
        self._outsideLightLevel_bright = 1

        # for tddi I2C control
        self._tddi_i2c_addr = 0x03
        self._tddi_enter_sleep_cmd = 0x10
        self._tddi_exit_sleep_cmd = 0x11
        self._tddi_disp_off_cmd = 0x28
        self._tddi_disp_on_cmd = 0x29

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

        self._ofs_st0_coeff_ram_ctrl_p0 = 0x5064
        self._ofs_st0_coeff_ram_ctrl_p1 = 0x5068
        self._ofs_ld_icon_indicator_p0 = 0x7000
        self._ofs_st0_ld_p63 = 0x81CC
        self._ofs_st0_ld_p66 = 0x81D8
        self._ofs_st0_ld_p67 = 0x81DC
        self._ofs_st0_ld_p68 = 0x81E0
        self._ofs_st0_ld_p69 = 0x81E4
        self._ofs_st0_ld_p70 = 0x81E8
        self._bitofs_st0_ld_led_edge_coeff_en = 3
        self._bitofs_st0_ld_led_coeff_en = 7
        self._ofs_ram_write_end = 0xFFFC

        # globla constants
        self.LD_PARAM_C__LOCAL_DIMMING_OFF = 0x0
        self.LD_PARAM_C__LOCAL_DIMMING_ON = 0x3
        self.LD_PARAM_AREA_CALC_OFS__OFF = 0x80
        self.LD_PARAM_AREA_CALC_OFS__DARK_MODE = 0x6E
        self.LD_PARAM_AREA_CALC_OFS__BRIGHT_MODE = 0x60

    def _forceResetSb7900(self, id):
        payload = [0x00, 0x02, 0x00, 0x20, 0x1E, 0x00, 0x00, 0x00]
        if id['mode'] == 'rombootloader':
            self.tc.sendCommand(self.tc.TOUCHCOMM_CMD_V2_ROMBOOT_MODE_WRITE_REGISTER, payload)
        elif id['mode'] == 'application':
            self.tc.sendCommand(self.tc.TOUCHCOMM_CMD_V2_APP_MODE_WRITE_REGISTER, payload)
        else:
            raise ValueError('Cannot write register in unknown mode: %s' % id['mode'])

        time.sleep(0.2) # wait a little for FW restart

    def powerOn(self):
        print("Power On Sequence")
        id = self.tc.identify()
        print(id)

        if id['mode'] == 'rombootloader':
            # due to unexpcted WDT at "runApplicationFirmware", force-reset first
            self._forceResetSb7900(id)
            self.isCoeffRamLoaded = False

        if id['mode'] == 'rombootloader':
            self.tc.runApplicationFirmware()
            id = self.tc.identify()
            print(id)

        if id['mode'] == 'application':
            self.isAppMode = True
            # send slpout/dispon into TDDI
            try:
                with SMBus(1) as bus:
                    msg = i2c_msg.write(self._tddi_i2c_addr, [self._tddi_disp_on_cmd])
                    bus.i2c_rdwr(msg)
                    msg = i2c_msg.write(self._tddi_i2c_addr, [self._tddi_exit_sleep_cmd])
                    bus.i2c_rdwr(msg)
            except OSError as e:
                # communication failed
                print(e)
            # readout local dimming configuration
            self.GetOutsideLightLevel()
            self.GetBrightness()
        else:
            self.isAppMode = False

        print("Power On Sequence Complete")

    def powerOff(self):
        try:
            # send slpin/dispoff into TDDI
            with SMBus(1) as bus:
                msg = i2c_msg.write(self._tddi_i2c_addr, [self._tddi_disp_off_cmd])
                bus.i2c_rdwr(msg)
                # wait at least 1 display frame
                time.sleep(0.1)
                msg = i2c_msg.write(self._tddi_i2c_addr, [self._tddi_enter_sleep_cmd])
                bus.i2c_rdwr(msg)
            # stop LVDS by entering BootROM when turn-off TDDI is succeeded
            self.tc.enterDisplayRomBootloaderMode()
        except OSError as e:
            # communication failed
            print(e)

    def getField(self, reg_addr, field_mask, field_ofs) -> int:
        ret = self.tc.readRegister(reg_addr, app_mode=self.isAppMode)
        return (ret & field_mask) >> field_ofs

    def setField(self, reg_addr, field_mask, field_ofs, val) -> None:
        ret = self.tc.readRegister(reg_addr, app_mode=self.isAppMode)
        reg_val = (ret & ~field_mask) | ((val << field_ofs) & field_mask)
        # FIXME: put delay between TCM v2 command makes stable operation...
        time.sleep(0.001)
        self.tc.writeRegister(reg_addr, reg_val, app_mode=self.isAppMode)

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

    def SetLocalDimmingMode(self, mode:int):
        TOUCHCOMM_CMD_SET_DIMMING_MODE = 135
        self.tc.sendCommand(TOUCHCOMM_CMD_SET_DIMMING_MODE, [mode])
        # I don't know why, but taking little delay makes more stable...
        time.sleep(0.01)
        self.tc.getResponse()
        # I don't know why, but taking little delay makes more stable...
        time.sleep(0.01)

    def EnableLocalDimming(self, enable : Union[bool, int]):
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p1
        field_ofs = self._bitofs_st0_c1_c0
        field_mask = self._mask_st0_c1_c0

        dimmingMode = 1
        if isinstance(enable, bool):
            if enable:
                val = self.LD_PARAM_C__LOCAL_DIMMING_ON
            else:
                val = self.LD_PARAM_C__LOCAL_DIMMING_OFF                
        elif isinstance(enable, int):
            if enable == 1:
                val = self.LD_PARAM_C__LOCAL_DIMMING_ON
            elif enable == 2:
                dimmingMode = 2
                val = self.LD_PARAM_C__LOCAL_DIMMING_ON
            else:
                val = self.LD_PARAM_C__LOCAL_DIMMING_OFF
        else:
            val = self.LD_PARAM_C__LOCAL_DIMMING_OFF

        self.SetLocalDimmingMode(dimmingMode)
        self.setField(reg_addr, field_mask, field_ofs, val)

    def EnableDarkSceneEnhancement(self, enable : bool):
        self.darkSceneEnabled = enable
        self.SetOutsideLightLevel(self.outsideLightLevel)

    def SetOutsideLightLevel(self, level : int):
        isChanged = (self.outsideLightLevel != level)
        self.outsideLightLevel = level
        val = self.LD_PARAM_AREA_CALC_OFS__OFF
        if (self.darkSceneEnabled):
            if (self.outsideLightLevel == self._outsideLightLevel_dark):
                val = self.LD_PARAM_AREA_CALC_OFS__DARK_MODE
            elif  (self.outsideLightLevel == self._outsideLightLevel_bright):
                val = self.LD_PARAM_AREA_CALC_OFS__BRIGHT_MODE

        self.setLdAreaCalcOfs(val)

        # Update brightness when needed
        if (isChanged or self.darkSceneEnabled):
            if (self.outsideLightLevel == self._outsideLightLevel_dark):
                self.SetBrightness(100)
            elif  (self.outsideLightLevel == self._outsideLightLevel_bright):
                self.SetBrightness(600)

    def GetOutsideLightLevel(self) -> int:
        val = self.getLdAreaCalcOfs()
        if (self.darkSceneEnabled):
            if (val == self.LD_PARAM_AREA_CALC_OFS__DARK_MODE):
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
        return int((self.brightness/50.0) + (1/2.0)) * 50

    def GetBrightnessIndex(self) -> int:
        self.brightness = self._coef_nit_per_dbv * self.getDbv()
        # [0-74]=0, [75-149]=1, [150-249]=2, ..., [1050-1149]=11, ...
        if self.brightness < 100:
          return int((self.brightness + 25)/100.0)
        else:
          return int((self.brightness + 50)/100.0)

    def SetDarkSceneEnhancementStrength(self, strength : int):
        val = 128 # off state
        if (self.darkSceneEnabled):
            # ST0_LD_P46.ST0_LD_AREA_CALC_OFS = 128 - strength
            val = 128 - strength
            if val < 0:
                val = 0
            if val > 128:
                val = 128

        self.setLdAreaCalcOfs(val)

    def GetDarkSceneEnhancementStrength(self) -> int:
        val = self.getLdAreaCalcOfs()
        strength = 128 - val
        if strength < 0:
            strength = 0
        if strength > 128:
            strength = 128

        return strength

    def setupLocalDimmingForLedBrokenDemo(self):
        self.EnableLocalDimming(True)
        self.EnableDarkSceneEnhancement(False)
        self.SetBrightness(500)

    def setupLdTellTale(self):
        # disable tellTale first
        self.setLdTellTaleEnable(False)

        # Configure defected LEDs
        # (11, 2),  (12, 2)
        # (11, 3),  (12, 3)
        bit_ofs0 = 11
        bit_ofs1 = 12
        reg_val = (1 << bit_ofs0) | (1 << bit_ofs1)
        for idx in range(2, 3+1):
            reg_ofs = 4 * idx
            reg_addr = self._base_disp_ctrl + self._ofs_ld_icon_indicator_p0 + reg_ofs
            self.tc.writeRegister(reg_addr, reg_val, app_mode=self.isAppMode)

    def setLdTellTaleEnable(self, mode: bool):
        # set ST0_LD_P63.ST0_LD_TELL_TALE_LED_VALUE_ON
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p63
        reg_val = 0x00000
        if mode:
          reg_val |= 1
        else:
          reg_val &= ~1

        self.tc.writeRegister(reg_addr, reg_val, app_mode=self.isAppMode)

    def setupLdCoeff(self):
        id = self.tc.identify()
        isAppMode = (id['mode'] == 'application')

        ld_enable_reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p1
        ld_enable_reg_val_back = self.tc.readRegister(ld_enable_reg_addr, app_mode=isAppMode)

        # turn-off local dimming first
        self.tc.writeRegister(ld_enable_reg_addr, 0, app_mode=self.isAppMode)

        # configure resigters
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p66
        self.tc.writeRegister(reg_addr, 0xFFFFFFFF, app_mode=self.isAppMode)
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p67
        self.tc.writeRegister(reg_addr, 0xFFFFFFFF, app_mode=self.isAppMode)
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p68
        self.tc.writeRegister(reg_addr, 0xFFFFFFFF, app_mode=self.isAppMode)
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p69
        self.tc.writeRegister(reg_addr, 0xFFFFFFFF, app_mode=self.isAppMode)

        # fill coeff RAM
        reg_addr = self._base_disp_ctrl + self._ofs_st0_coeff_ram_ctrl_p0
        self.tc.writeRegister(reg_addr, 0, app_mode=self.isAppMode)
        reg_addr = self._base_disp_ctrl + self._ofs_st0_coeff_ram_ctrl_p1
        print("Wait a moment...")
        for idx in range(int(32 * 12 / 4)):
            if idx == 10:
                self.tc.writeRegister(reg_addr, 0xF0F08080, app_mode=isAppMode)
            elif idx == 11:
                self.tc.writeRegister(reg_addr, 0x8080F0F0, app_mode=isAppMode)
            elif idx == 18:
                self.tc.writeRegister(reg_addr, 0x00F08080, app_mode=isAppMode)
            elif idx == 19:
                self.tc.writeRegister(reg_addr, 0x8080F000, app_mode=isAppMode)
            elif idx == 26:
                self.tc.writeRegister(reg_addr, 0x00F08080, app_mode=isAppMode)
            elif idx == 27:
                self.tc.writeRegister(reg_addr, 0x8080F000, app_mode=isAppMode)
            elif idx == 34:
                self.tc.writeRegister(reg_addr, 0xF0F08080, app_mode=isAppMode)
            elif idx == 35:
                self.tc.writeRegister(reg_addr, 0x8080F0F0, app_mode=isAppMode)
            else:
                self.tc.writeRegister(reg_addr, 0x80808080, app_mode=isAppMode)
        print("Done")

        reg_addr = self._base_disp_ctrl + self._ofs_ram_write_end
        self.tc.writeRegister(reg_addr, 0, app_mode=isAppMode)

        # restore local dimming again
        self.tc.writeRegister(ld_enable_reg_addr, ld_enable_reg_val_back, app_mode=isAppMode)

        self.isCoeffRamLoaded = True

    def setLdCoeffEnable(self, mode: bool):
        # set ST0_LD_P70.ST0_LD_LED_COEFF_ON and ST0_LD_P70.ST0_LD_EDGE_COEFF_ON
        reg_addr = self._base_disp_ctrl + self._ofs_st0_ld_p70
        reg_val = self.tc.readRegister(reg_addr, app_mode=self.isAppMode)
        mode_mask = (1 << self._bitofs_st0_ld_led_edge_coeff_en) | (1 << self._bitofs_st0_ld_led_coeff_en)
        if mode:
            reg_val |= mode_mask
        else:
            reg_val &= ~mode_mask

        self.tc.writeRegister(reg_addr, reg_val, app_mode=self.isAppMode)

    def SetLedDefectDemoMode(self, mode: int):
        if mode == 2:
            self.setLdTellTaleEnable(True)
            self.setLdCoeffEnable(True)
        elif mode == 1:
            self.setLdCoeffEnable(False)
            self.setLdTellTaleEnable(True)
        else:
            self.setupLocalDimmingForLedBrokenDemo()
            self.setupLdTellTale()
            if not self.isCoeffRamLoaded:
                self.setupLdCoeff()
            self.setLdTellTaleEnable(False)
            self.setLdCoeffEnable(False)

if __name__ == "__main__":
    pass
