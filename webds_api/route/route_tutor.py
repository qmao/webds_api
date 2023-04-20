import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
import sys
import time
import re
from ..tutor.tutor_utils import EventQueue

### auto import tutor routes from webds_api
for folder in os.scandir("/usr/local/lib/python3.7/dist-packages/webds_api/tutor"):
    if folder.is_dir():
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.endswith('_route.py'):
                string = f'from ..tutor.{folder.name}.{entry.name[:-3]} import *'
                exec (string)

class TutorHandler(APIHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, name, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: {}\n'.format(name))
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()

        except StreamClosedError:
            print("stream close error!!")
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def getSSE(self):
        print("SSE LOOP")
        queue = EventQueue()
        queue.reset()

        try:
            while True:
                name, info = queue.pop()
                if info is not None:
                    yield self.publish(name, json.dumps(info))
                if not queue.is_alive():
                    break
                yield tornado.gen.sleep(0.0001)

        except StreamClosedError:
            print("Stream Closed!")
            pass

        except Exception as e:
            ### TypeError
            ### BrokenPipeError
            print("Oops! get report", e.__class__, "occurred.")
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        finally:
            print("terminate")
            queue.terminate()

    @tornado.web.authenticated
    def get(self, subpath: str = "", cluster_id: str = ""):
        print("self.request:", self.request)
        print("subpath:",subpath)

        data = json.loads("{}")

        try:
            paths = subpath.split("/")
            print("[PATH]", paths)
            if len(paths) == 1:
                if paths[0] == "event":
                    return self.getSSE()
                else:
                    tutor = TutorHandler.get_tutor_route_str(paths[0])
                    cls = globals()[tutor]
                    function = getattr(cls, 'get')
                    data = function(self)
            else:
                print("TBC")
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
        try:
            paths = subpath.split("/")

            if len(paths) == 1:
                tutor = TutorHandler.get_tutor_route_str(paths[0])
                cls = globals()[tutor]
                function = getattr(cls, 'post')
                data = function(self, input_data)

        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        print("--- %s seconds ---" % (time.time() - start_time))

        self.finish(json.dumps(data))

    def camel_case_to_snake_case(name):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    def get_tutor_route_str(name):
        EventQueue().set_module_name(name)
        name = name + "Route"
        return name