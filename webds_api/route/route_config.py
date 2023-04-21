import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
import time
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError, HttpNotFound


class ConfigHandler(APIHandler):

    def _set_static_config(static):
        tc = TouchcommManager()
        tc.function("getAppInfo")

        arg = tc.getInstance().decoder.encodeStaticConfig(static)

        try:
            tc.function("sendCommand", args = [34, arg])
            tc.function("getResponse")
        except:
            try:
                tc.function("sendCommand", args = [56])
                tc.function("getResponse")

                tc.function("sendCommand", args = [57, arg])
                tc.function("getResponse")

                tc.function("sendCommand", args = [55])
                tc.function("getResponse")
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
            raise HttpServerError(message)
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
            raise HttpNotFound()
        else:
            raise HttpNotFound()

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
                raise HttpNotFound()

        except Exception as e:
            print("Exception...", e)

        data = json.loads("{}")
        self.finish(data)