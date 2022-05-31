import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from . import webds
from .utils import SystemHandler
from .touchcomm_manager import TouchcommManager


class ConfigHandler(APIHandler):

    def _set_static_config(static):
        _tc = TouchcommManager().getInstance()
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
            except:
                print("Set static config failed")
                #### error handling

    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        configToSet = self.get_json_body()
        print(configToSet)

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

            self.set_header('content-type', 'application/json')
            self.finish(json.dumps(config))

        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

    @tornado.web.authenticated
    def get(self):

        print(self.request.arguments)

        config_type = self.get_argument('type', None)

        tc = TouchcommManager()
        try:
            if config_type == 'static':
                config = tc.function("getStaticConfig")
                print(config)
                self.finish(json.dumps(config))
                return
            elif config_type == 'dynamic':
                config = tc.function("getDynamicConfig")
                print(config)
                self.finish(json.dumps(config))
                return

        except Exception as e:
            print("Exception...", e)

        data = json.loads("{}")
        self.finish(data)