from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .max_capacitance import MaxCapacitance

g_process = None
g_tutor = None

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
                if g_tutor is not None:
                    g_tutor.reset()
                return {"state": "done"}
            elif task == "terminate":                
                if g_process is not None:
                    g_process.kill()
                    g_process.join()
                EventQueue().close()
                return {"state": "done"}
            else:
                raise Exception('Unsupport parameters: ', input_data)
        except Exception as e:
            raise Exception('MaxCapacitance Manager Post error: ', str(e))

    def run():
        global g_process
        g_process = Process(target=MaxCapacitanceRoute.tune)
        g_process.start()

        return {"data": "start"}

    def tune():
        global g_tutor

        tc = TouchcommManager().getInstance()
        g_tutor = MaxCapacitance(tc)

        g_tutor.init()
        t_max_prev = 0
        t_cum_max_prev = 0
        while True:
            t_max, t_cum_max = g_tutor.run()
            EventQueue().push({"state": "run", "value": {"max": int(t_max), "cum_max": int(t_cum_max)}})
            t_max_prev = t_max
            t_cum_max_prev = t_cum_max
