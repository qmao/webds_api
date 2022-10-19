import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from .localcbc_manager import LocalCBCManager

g_thread = None

class LocalCBC():
    def get(handle):
        raise Exception('Unsupport function:', __class__, __name__)

    def post(handle, input_data):
        print(input_data)
        task = input_data["task"]
        frame_count = input_data["settings"]["frameCount"]

        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)

        if task == "run":
            return LocalCBC.run(frame_count)
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        task = LocalCBCManager()
        global g_thread
        if g_thread is not None and g_thread.is_alive():
            raise Exception('Prev thread is running')

        g_thread = threading.Thread(target=task.run, args=(params, ))
        g_thread.start()
        print("thread start")
        return {"data": "start"}