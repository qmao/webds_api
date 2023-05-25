import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from uuid import uuid4

from ..utils import SystemHandler
from ..errors import HttpServerError


rand_token = str(uuid4())

class GeneralHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        print(self.request)

        SystemHandler.UpdateWorkspace()

        self.finish(json.dumps({
            "data": "webds_api server is running"
        }))

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        print(data)
        response = {}

        if "command" in data:
            param = data["command"]
            print(param)
            if "action" in param and param["action"] == "reboot":
                print("reboot")
                if "target" in param and param["target"] == "rpi4":
                    print("reboot rpi4")
                    global rand_token
                    print(rand_token)
                    if "token" in param:
                        print("token found")
                        token = param["token"]
                        print(token)
                        if token == rand_token:
                            print("token matched")
                            self.finish(json.dumps("done"))
                            SystemHandler.CallSysCommandFulfil('reboot')
                            return
                        else:
                            print("token not matched")
                            raise HttpServerError("token not matched")
                    else:
                        rand_token = str(uuid4())
                        print(rand_token)
                        self.finish(json.dumps(rand_token))
                        return
                else:
                    print("target not set")
        else:
            print("command not set")

        raise HttpServerError("unsupported action")