import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from .localcbc_manager import LocalCBCManager

g_thread = None

class LocalCBC():
    def get(handle):
        try:
            data = LocalCBCManager().run()
        except Exception as e:
            return {"error": str(e)}
        return {"data": "start"}

    def post(handle, input_data):
        print(input_data)
        task = input_data["task"]
        
        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)

        if task == "run":
            return LocalCBC.run()
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run():
        task = LocalCBCManager()
        global g_thread
        if g_thread is not None and g_thread.is_alive():
            raise Exception('Prev thread is running')

        g_thread = threading.Thread(target=task.run)
        g_thread.start()
        print("thread start")
        return {"data": "start"}