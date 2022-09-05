import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json

from .. import webds
from ..program.programmer_manager import ProgrammerManager
from ..touchcomm.touchcomm_manager import TouchcommManager

import threading
from queue import Queue
import time
import sys

from tornado import gen
from tornado.iostream import StreamClosedError

g_stdout_handler = None
g_program_thread = None

class StdoutHandler(Queue):
    _progress = 0
    _status = 'idle'
    _message = None

    def __init__(self):
        super().__init__()

    def write(self,msg):
        try:
            if "%" in msg:
                progress = msg[12:-1]
                self._progress = int(progress, base=10)
            sys.__stdout__.write(msg)
        except Exception as e:
            print("Oops StdoutHandler write!", e.__class__, "occurred.")
            pass

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
        

class ProgramHandler(APIHandler):
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
            self.write('event: reprogram\n')
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
                if g_stdout_handler is not None:
                    status = g_stdout_handler.get_status()
                    if status == 'start':
                        if self._last != g_stdout_handler.get_progress():
                            send = {
                                "progress": g_stdout_handler.get_progress(),
                            }
                            yield self.publish(json.dumps(send))
                            self._last = g_stdout_handler.get_progress()
                    elif status != 'start' and status != 'idle':
                        print(g_stdout_handler.get_message())
                        send = {
                            "progress": g_stdout_handler.get_progress(),
                            "status": status,
                            "message": g_stdout_handler.get_message()
                        }
                        print(json.dumps(send))
                        yield self.publish(json.dumps(send))
                        g_stdout_handler.reset()

                        self.finish(json.dumps({
                            "data": "done"
                        }))
                        break
                    yield gen.sleep(0.0001)
                else:
                    yield gen.sleep(1)

        except StreamClosedError:
            message="stream closed"
            print(message)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        print("request progress finished")

    @tornado.web.authenticated
    def post(self):
        # input_data is a dictionary with a key "filename"
        input_data = self.get_json_body()
        print(input_data)
        data = ""

        global g_stdout_handler
        global g_program_thread

        action = input_data["action"]
        if action == "start":
            print("start to erase and program!!!")

            filename = os.path.join(webds.PACKRAT_CACHE, input_data["filename"])
            print(filename)

            if not os.path.isfile(filename):
                message = "HEX file not found: " + filename
                raise tornado.web.HTTPError(status_code=400, log_message=message)

            if g_program_thread is not None and g_program_thread.is_alive():
                print("erase and program thread is still running...")
                g_program_thread.join()
                print("previous erase and program thread finished.")

            if g_stdout_handler is None:
                print("create StdoutHandler")
                g_stdout_handler = StdoutHandler()

            g_program_thread = threading.Thread(target=self.program, args=(filename, g_stdout_handler))
            g_program_thread.start()
            print("program thread start")
            ### g_program_thread.join()

            data = {
              "status": g_stdout_handler.get_status(),
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

    def program(self, filename, handler):
        temp = sys.stdout
        sys.stdout = handler

        handler.set_status("start")
        try:
            ret = ProgrammerManager.program(filename)
            sys.stdout = temp

            if handler.get_progress() != 100:
                print(handler.get_progress())
                handler.set_message("Unkwon error")
                handler.set_progress(-1)
                handler.set_status("error")
            else:
                print("Erase and program done.")

                TouchcommManager().getInstance()
                handler.set_message("Programmed with " + filename)
                handler.set_status("success")

        except Exception as error:
            print(error)
            handler.set_progress(-1)
            handler.set_message(str(error))
            handler.set_status("error")
