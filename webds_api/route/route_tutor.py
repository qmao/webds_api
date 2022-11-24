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
from ..tutor.tutor_utils import SSEQueue

from ..tutor.localcbc.localcbc import LocalCBC
from ..tutor.max_capacitance.max_capacitance import MaxCapacitance
from ..tutor.int_dur.int_dur import IntDur

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
        queue = SSEQueue()
        queue.reset()

        try:
            while True:
                name, info = queue.getQueue()
                if info is not None:
                    if info["state"] == "stop":
                        yield self.publish(name, json.dumps(info))
                        self.finish(json.dumps({}))
                        break
                    elif info["state"] == "terminate":
                        yield self.publish(name, json.dumps(info))
                        self.finish(json.dumps({}))
                        break
                    else:
                        ### runing
                        yield self.publish(name, json.dumps(info))

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
                    tutor = paths[0]
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
                tutor = paths[0]
                cls = globals()[tutor]
                function = getattr(cls, 'post')
                data = function(self, input_data)

        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        print("--- %s seconds ---" % (time.time() - start_time))

        self.finish(json.dumps(data))