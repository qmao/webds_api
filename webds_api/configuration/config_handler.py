import json
import time
import sys


class ConfigHandler():
    _static_config = {}
    _dynamic_config = {}
    _touch_info = {}
    _app_info = {}
    _tc = None

    @classmethod
    def init(cls, tc):
        cls._tc = tc
        cls._app_info = tc.getAppInfo()
        cls._static_config = cls.get_static_config()
        cls._dynamic_config = cls.get_dynamic_config()

    @classmethod
    def commit_config(cls):
        return cls._tc.commitConfig()

    @classmethod
    def get_static_config(cls):
        if not cls._static_config:
            cls._static_config = cls._tc.getStaticConfig()
            ### print("[Static Config]", cls._static_config)
            ### v = cls._tc.decoder.encodeStaticConfig(cls._static_config)
            ### print("[Static Config hex]", ''.join('{:02x}'.format(x) for x in v))
        return cls._static_config

    @classmethod
    def get_dynamic_config(cls):
        if not cls._dynamic_config:
            cls._dynamic_config = cls._tc.getDynamicConfig()
            ### print("[Dynamic Config]", cls._dynamic_config)
            ### v = cls._tc.decoder.encodeDynamicConfig(cls._dynamic_config)
            ### print("[Dynamic Config hex]", ''.join('{:02x}'.format(x) for x in v))
        return cls._dynamic_config

    @classmethod
    def get_touch_info(cls):
        if not cls._touch_info:
            cls._touch_info = cls._tc.getTouchInfo()
        return cls._touch_info

    @classmethod
    def get_app_info(cls):
        return cls._app_info

    @classmethod
    def restore(cls):
        cls.set_static_config(cls._static_config)
        cls.set_dynamic_config(cls._dynamic_config)

    @classmethod
    def set_static_config(cls, config):
        tc = cls._tc
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

    @classmethod
    def set_dynamic_config(cls, config):
        cls._tc.setDynamicConfig(config)

    @classmethod
    def update_static_config(cls, configToSet):
        try:
            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        cls._static_config[key][idx] = int(x)
                else:
                    cls._static_config[key] = int(config_value)

            cls.set_static_config(cls._static_config)

        except Exception as e:
            raise Exception(str(e))
        return cls._static_config

    @classmethod
    def update_dynamic_config(cls, configToSet):
        try:
            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        cls._dynamic_config[key][idx] = int(x)
                else:
                    cls._dynamic_config[key] = int(config_value)

            cls.set_dynamicConfig(cls._dynamic_config)

        except Exception as e:
            raise Exception(str(e))
        return cls._dynamic_config
