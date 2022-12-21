import tornado
from tornado.iostream import StreamClosedError
from tornado import gen

import threading
from .max_capacitance import MaxCapacitance

g_max_capacitance_thread = None
g_max_capacitance_handle = None

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
                return MaxCapacitanceRoute.run()
            elif task == "reset":
                if g_max_capacitance_handle is not None:
                    return g_max_capacitance_handle.reset()
                return {"done"}
            elif task == "terminate":
                if g_max_capacitance_handle is not None:
                    return g_max_capacitance_handle.terminate()
                return {"done"}
            else:
                raise Exception('Unsupport parameters: ', input_data)
        except Exception as e:
            raise Exception('MaxCapacitance Manager Post error: ', str(e))

    def run():
        global g_max_capacitance_handle
        g_max_capacitance_handle = MaxCapacitance()

        global g_max_capacitance_thread
        if g_max_capacitance_thread is not None and g_max_capacitance_thread.is_alive():
            raise Exception('Prev thread is running')

        g_max_capacitance_thread = threading.Thread(target=g_max_capacitance_handle.run)
        g_max_capacitance_thread.start()
        print("thread start")
        return {"data": "start"}