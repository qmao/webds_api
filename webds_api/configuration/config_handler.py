import json
import time
import sys

sys.path.append('/usr/local/lib/python3.7/dist-packages/webds_api/touchcomm')
from touchcomm_manager import TouchcommManager


class ConfigHandler():
    _static_config = {}
    _dynamic_config = {}
    _touch_info = {}
    _app_info = {}
    _tc = None

    def __init__(self, tc):
        self._app_info = tc.getInstance().getAppInfo()
        self._tc = tc

    def getStaticConfig(self):
        if not self._static_config:
            self._static_config = self._tc.getInstance().getStaticConfig()
            ### print("[Static Config]", self._static_config)
            ### v = self._tc.getInstance().decoder.encodeStaticConfig(self._static_config)
            ### print("[Static Config hex]", ''.join('{:02x}'.format(x) for x in v))
        return self._static_config

    def getDynamicConfig(self):
        if not self._dynamic_config:
            self._dynamic_config = self._tc.getInstance().getDynamicConfig()
            ### print("[Dynamic Config]", self._dynamic_config)
            ### v = self._tc.getInstance().decoder.encodeDynamicConfig(self._dynamic_config)
            ### print("[Dynamic Config hex]", ''.join('{:02x}'.format(x) for x in v))
        return self._dynamic_config

    def getTouchInfo(self):
        if not self._touch_info:
            self._touch_info = self._tc.getInstance().getTouchInfo()
        return self._touch_info

    def getAppInfo(self):
        return self._app_info

    def setStaticConfig(self, config):
        tc = self._tc.getInstance()
        v = tc.decoder.encodeStaticConfig(config)
        try:
            tc.sendCommand(34, v)
            tc.getResponse()
            time.sleep(0.1)
        except Exception as e:
            tc.sendCommand(56)
            tc.getResponse()
            time.sleep(0.1)

            tc.sendCommand(57, v)
            tc.getResponse()
            time.sleep(0.1)

            tc.sendCommand(55)
            tc.getResponse()
            time.sleep(0.1)

    def setDynamicConfig(self, config):
        self._tc.getInstance().setDynamicConfig(config)

    def update_static_config(self, configToSet):
        try:
            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        self._static_config[key][idx] = int(x)
                else:
                    self._static_config[key] = int(config_value)

            self.setStaticConfig(self._static_config)

        except Exception as e:
            raise Exception(str(e))
        return self._static_config

    def update_dynamic_config(self, configToSet):
        try:
            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        self._dynamic_config[key][idx] = int(x)
                else:
                    self._dynamic_config[key] = int(config_value)

            self.setDynamicConfig(self._dynamic_config)

        except Exception as e:
            raise Exception(str(e))
        return self._dynamic_config
