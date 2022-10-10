import json
import time
from ..touchcomm.touchcomm_manager import TouchcommManager


class ConfigHandler():
    def _set_static_config(static, handle=None):
        if handle is None:
            _tc = TouchcommManager().getInstance()
        else:
            _tc = handle.getInstance()
        _tc.reset()
        _tc.getAppInfo()

        arg = _tc.decoder.encodeStaticConfig(static)

        try:
            _tc.sendCommand(34, arg)
            _tc.getResponse()
        except:
            try:
                _tc.sendCommand(56)
                _tc.getResponse()

                _tc.sendCommand(57, arg)
                _tc.getResponse()

                _tc.sendCommand(55)
                _tc.getResponse()
                time.sleep(0.1)
            except Exception as e:
                raise Exception(str(e))
                print("Set static config failed")
                #### error handling

    def _update_static_config(configToSet, handle=None):
        try:
            if handle is None:
                tc = TouchcommManager()
            else:
                tc = handle
            config = tc.function("getStaticConfig")

            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        config[key][idx] = int(x)
                else:
                    config[key] = int(config_value)
            ConfigHandler._set_static_config(config, tc)
        except Exception as e:
            raise Exception(str(e))
        return config