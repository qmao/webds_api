import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from .localcbc import Localcbc

g_thread = None
g_handle = None

class LocalCBCRoute():
    def get(handle):
        raise Exception('Unsupport function:', __class__, __name__)

    def post(handle, input_data):
        print(input_data)
        task = input_data["task"]

        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)

        if task == "run":
            frame_count = input_data["settings"]["frameCount"]
            return LocalCBCRoute.run(frame_count)
        elif task == "terminate":
            return g_handle.terminate()
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        global g_handle
        g_handle = Localcbc()
        global g_thread
        if g_thread is not None and g_thread.is_alive():
            raise Exception('Prev thread is running')

        g_thread = threading.Thread(target=g_handle.run, args=(params, ))
        g_thread.start()
        print("thread start")
        return {"data": "start"}