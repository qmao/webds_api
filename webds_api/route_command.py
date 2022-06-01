import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from . import webds
from .utils import SystemHandler
from .touchcomm_manager import TouchcommManager


class CommandHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        input_data = self.get_json_body()
        print(input_data)

        command = input_data["command"]
        if "payload" in input_data:
            payload = input_data["payload"]
        else:
            payload = None

        print(command)
        print(payload)

        try:
            tc = TouchcommManager()
            tc.function(command, payload)
        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        data = {'data': 'done'}
        self.set_header('content-type', 'application/json')
        self.finish(json.dumps(data))


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
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        data = json.loads("{}")
        self.finish(data)