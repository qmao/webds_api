import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json

from ..errors import HttpBrokenPipe, HttpStreamClosed, HttpServerError
from .. import webds
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..device.device_info import DeviceInfo

import threading
from queue import Queue
import time
import sys
import re

from tornado import gen
from tornado.iostream import StreamClosedError

g_status_handler = None
g_thread = None


class StatusHandler(Queue):
    _progress = 0
    _status = 'idle'
    _message = None

    def __init__(self):
        super().__init__()

    def write(self,msg):
        try:
            if "/" in msg:
                m = re.search('(\d+)(?=/\d+)', msg)
                if m is not None:
                    self._progress = int(m.group(0), base=10)
            sys.__stdout__.write(msg)
        except Exception as e:
            raise BrokenPipe(str(e))

    def flush(self):
        sys.__stdout__.flush()

    def get_progress(self):
        return self._progress

    def set_progress(self, num):
        self._progress = num

    def reset(self):
        self._status = 'idle'
        self._progress = 0
        self._message = ''

    def set_status(self, status):
        self._status = status

    def get_status(self):
        return self._status

    def get_message(self):
        return self._message

    def set_message(self, message):
        self._message = message

class ReflashHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    def initialize(self):
        self._last = 0
        self.set_header('cache-control', 'no-cache')

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: reflash\n')
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()

        except StreamClosedError:
            print("stream close error!!")
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        print("request progress")
        try:
            while True:
                if g_status_handler is not None:
                    status = g_status_handler.get_status()
                    if status == 'start':
                        if self._last != g_status_handler.get_progress():
                            send = {
                                "progress": g_status_handler.get_progress(),
                            }
                            yield self.publish(json.dumps(send))
                            self._last = g_status_handler.get_progress()
                    elif status != 'start' and status != 'idle':
                        send = {
                            "progress": g_status_handler.get_progress(),
                            "status": status,
                            "message": g_status_handler.get_message()
                        }
                        print(json.dumps(send))
                        yield self.publish(json.dumps(send))
                        g_status_handler.reset()

                        self.finish(json.dumps({
                            "data": "done"
                        }))
                        break
                    yield gen.sleep(0.0001)
                else:
                    yield gen.sleep(1)

        except StreamClosedError:
            raise HttpStreamClosed()

        print("request progress finished")

    @tornado.web.authenticated
    def post(self):
        # input_data is a dictionary with a key "filename"
        input_data = self.get_json_body()
        print(input_data)
        data = ""

        global g_status_handler
        global g_thread

        action = input_data["action"]
        if action == "start":
            print("start to reflash!!!")

            filename = os.path.join(webds.PACKRAT_CACHE, input_data["filename"])
            print(filename)

            if not os.path.isfile(filename):
                message = "file not found: " + filename
                raise HttpServerError(message)

            if g_thread is not None and g_thread.is_alive():
                print("thread is still running...")
                g_thread.join()
                print("previous thread finished.")

            if g_status_handler is None:
                print("create StatusHandler")
                g_status_handler = StatusHandler()

            g_thread = threading.Thread(target=self.reflash, args=(filename, g_status_handler))
            g_thread.start()

            data = {
              "status": g_status_handler.get_status(),
            }
            print(data)

        elif action == "cancel":
            print("cancel thread")
            data = {
              "status": "TBC",
            }

        else:
            print("unknown action" + action)

        print(data)
        self.finish(json.dumps(data))

    def reflash(self, filename, handler):
        print("reflash thread start")
        temp = sys.stdout
        sys.stdout = handler

        try:
            handler.set_status("start")

            tc = TouchcommManager()

            info = DeviceInfo.identify_type(tc)
            tc.function("reflashImageFile", args = [filename, info["is_multi_chip"], info["has_touchcomm_storage"], False])
            id = tc.function("runApplicationFirmware")
            print(id)

            if handler.get_progress() != 100:
                print(handler.get_progress())
                handler.set_message("Unkwon error")
                handler.set_progress(-1)
                handler.set_status("error")
            else:
                handler.set_message("Reflash with " + filename)
                handler.set_status("success")

        except Exception as error:
            print(error)
            handler.set_progress(-1)
            handler.set_message(str(error))
            handler.set_status("error")
        finally:
            sys.stdout = temp
