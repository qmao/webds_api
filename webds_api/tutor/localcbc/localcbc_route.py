import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import math
import threading
import multiprocessing
import logging

from multiprocessing import Process, Pool
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import SSEQueue
from .localcbc import LocalCBC

g_queue = None
g_process = None

class LogHandler(logging.Handler):
    def emit(self, record):
        progress = math.floor(float(record.getMessage()))
        send_event({"state": "run", "progress": progress})

def send_event(event):
        global g_queue
        if g_queue is None:
            g_queue = SSEQueue()
        g_queue.send_event(event)

class LocalCBCRoute():
    def get(handle):
        raise Exception('Unsupport function:', __class__, __name__)

    def post(handle, input_data):
        task = input_data["task"]

        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)

        if task == "run":
            frame_count = input_data["settings"]["frameCount"]
            return LocalCBCRoute.run(frame_count)
        elif task == "terminate":
            send_event({"state": "terminate"})
            if g_process is not None:
                g_process.kill()
                ##g_process.terminate()
                g_process.join()
                send_event({"data": "cancel"})
            return
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        send_event({"state": "init"})

        global g_process
        g_process = Process(target=LocalCBCRoute.tune, args=(params, ))
        g_process.start()

        return {"data": "start"}

    def done(result):
        send_event({"state": "stop", "data": result})

    def tune(params):
        print("thread run")

        logging.getLogger('tuningProgress').addHandler(LogHandler())

        tc = TouchcommManager().getInstance()
        g_tutor = LocalCBC(tc)

        result = g_tutor.run(params)

        send_event({"state": "stop", "data": result})