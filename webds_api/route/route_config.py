import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
import time
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager


class ConfigHandler(APIHandler):

    def _set_static_config(static):
        _tc = TouchcommManager().getInstance()
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
                print("Set static config failed:", str(e))
                #### error handling

    def _update_static_config(configToSet):
        try:
            tc = TouchcommManager()
            config = tc.function("getStaticConfig")

            for key in configToSet:
                config_value = configToSet[key]
                print(key, '->', config_value)
                if isinstance(config_value, list):
                    for idx, x in enumerate(config_value):
                        config[key][idx] = int(x)
                else:
                    config[key] = int(config_value)
            ConfigHandler._set_static_config(config)
        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)
        return config

    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self, config_type):
        configToSet = self.get_json_body()
        print(configToSet)

        if config_type == 'static':
            config = ConfigHandler._update_static_config(configToSet)
        elif config_type == 'dynamic':
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        else:
            raise tornado.web.HTTPError(status_code=405, log_message="Not support")

        self.set_header('content-type', 'application/json')
        self.finish(json.dumps(config))

    @tornado.web.authenticated
    def get(self, config_type):

        print(self.request.arguments)
        print(config_type)

        tc = TouchcommManager()
        try:
            if config_type == 'static':
                config = tc.function("getStaticConfig")
                self.finish(json.dumps(config))
                return
            elif config_type == 'dynamic':
                config = tc.function("getDynamicConfig")
                self.finish(json.dumps(config))
                return
            else:
                raise tornado.web.HTTPError(status_code=405, log_message="Not support")

        except Exception as e:
            print("Exception...", e)

        data = json.loads("{}")
        self.finish(data)