import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import SSEQueue
from .max_capacitance import MaxCapacitance

g_thread = None
g_tutor = None
g_queue = None

module_name = "MaxCapacitance"

class MaxCapacitanceRoute():
    def get(handle):
        try:
            data = MaxCapacitanceRoute().run()
        except Exception as e:
            return {"error": str(e)}
        return {"data": "start"}

    def post(handle, input_data):
        print(input_data)
        task = input_data["task"]
        
        try:
            if task == None:
                raise Exception('Unsupport input parameters: ', input_data)

            if task == "run":
                return MaxCapacitanceRoute.setup()
            elif task == "reset":
                if g_tutor is not None:
                    g_tutor.reset()
                return {"state": "done"}
            elif task == "terminate":
                MaxCapacitanceRoute.callback({"state": "terminate"})
                if g_tutor is not None:
                    g_tutor.terminate()
                return {"state": "done"}
            else:
                raise Exception('Unsupport parameters: ', input_data)
        except Exception as e:
            raise Exception('MaxCapacitance Manager Post error: ', str(e))

    def setup():
        global g_thread
        if g_thread is not None and g_thread.is_alive():
            raise Exception('Prev thread is running')

        g_thread = threading.Thread(target=MaxCapacitanceRoute.run)
        g_thread.start()
        print("thread start")
        return {"data": "start"}

    def callback(event):
        global g_queue
        if g_queue is None:
            g_queue = SSEQueue()
        g_queue.setInfo(module_name, event)

    def run():
        print("thread run")
        global g_tutor

        tc = TouchcommManager().getInstance()
        g_tutor = MaxCapacitance(tc, MaxCapacitanceRoute.callback)

        data = g_tutor.run()
        MaxCapacitanceRoute.callback({"state": "stop", "data": data})

        print("thread finished!!!")