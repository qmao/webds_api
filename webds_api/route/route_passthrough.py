import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
import sys
from importlib import import_module
import importlib.util
import time

class PassthroughHandler(APIHandler):
    @tornado.web.authenticated
    def get(self, subpath: str = "", cluster_id: str = ""):
        print("self.request:", self.request)
        print("subpath:",subpath)

        data = json.loads("{}")

        try:
            paths = subpath.split("/")
            print("[PATH]", paths)
            if len(paths) == 1:
                pyfile = paths[0]
                pyfunction="test"

                spec = importlib.util.spec_from_file_location(pyfile, "/home/dsdkuser/jupyter/workspace/" + pyfile + ".py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                function = self.get_argument('function', None)
                param = self.get_argument('param', None)

                mymethod = getattr(module, function)
                if param:
                    data = mymethod(param)
                else:
                    data = mymethod()
                print("ret", data)
            else:
                raise tornado.web.HTTPError(status_code=400, log_message="not implement")
        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        self.finish(json.dumps(data))

    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        input_data = self.get_json_body()
        print(input_data)

        start_time = time.time()
        print("self.request:", self.request)
        print("subpath:",subpath)

        data = json.loads("{}")

        try:
            paths = subpath.split("/")
            print("[PATH]", paths)
            if len(paths) == 1:
                pyfile = paths[0]
                pyfunction="test"

                spec = importlib.util.spec_from_file_location(pyfile, "/home/dsdkuser/jupyter/workspace/" + pyfile + ".py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                function = input_data["function"]
                param = input_data["param"]

                mymethod = getattr(module, function)
                if param:
                    data = mymethod(param)
                else:
                    data = mymethod()
                print("ret", data)
            else:
                raise tornado.web.HTTPError(status_code=400, log_message="not implement")
        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)


        print("--- %s seconds ---" % (time.time() - start_time))

        self.finish(json.dumps(data))
