import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError


class CommandHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        input_data = self.get_json_body()
        print(input_data)

        try:
            command = input_data["command"]
            if "payload" in input_data:
                payload = input_data["payload"]
            else:
                payload = None

            print(command)
            print(payload)

            tc = TouchcommManager()
            response = tc.function(command, payload)
        except Exception as e:
            raise HttpServerError(str(e))

        self.finish(json.dumps(response))

    @tornado.web.authenticated
    def get(self):

        print(self.request.arguments)

        query = self.get_argument('query', None)

        try:
            tc = TouchcommManager()
            if query == 'app-info':
                info = tc.function('getAppInfo')
                self.finish(json.dumps(info))
                return
            else:
                info = tc.function(query)
                self.finish(json.dumps(info))
                return

        except Exception as e:
            raise HttpServerError(str(e))

        data = json.loads("{}")
        self.finish(data)