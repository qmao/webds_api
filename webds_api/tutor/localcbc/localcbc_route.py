import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import SSEQueue
from .localcbc import LocalCBC

g_thread = None
g_tutor = None
g_queue = None

MODULE_NAME = "LocalCBC"

class LocalCBCRoute():
    def get(handle):
        raise Exception('Unsupport function:', __class__, __name__)

    def post(handle, input_data):
        task = input_data["task"]

        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)

        if task == "run":
            frame_count = input_data["settings"]["frameCount"]
            return LocalCBCRoute.setup(frame_count)
        elif task == "terminate":
            LocalCBCRoute.callback({"state": "terminate"})
            if g_tutor is not None:
                g_tutor.terminate()
            return
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def setup(params):
        global g_thread
        if g_thread is not None and g_thread.is_alive():
            raise Exception('Prev thread is running')

        g_thread = threading.Thread(target=LocalCBCRoute.run, args=(params, ))
        g_thread.start()
        print("thread start")
        return {"data": "start"}

    def callback(event):
        global g_queue
        if g_queue is None:
            g_queue = SSEQueue()
        g_queue.setInfo(MODULE_NAME, event)

    def run(params):
        print("thread run")
        global g_tutor

        tc = TouchcommManager().getInstance()
        g_tutor = LocalCBC(tc, LocalCBCRoute.callback)

        data = g_tutor.run(params)
        LocalCBCRoute.callback({"state": "stop", "data": data})

        print("thread finished!!!")