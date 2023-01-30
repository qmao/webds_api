from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .max_capacitance import MaxCapacitance
from ..tutor_wrapper import *


class MaxCapacitanceRoute():
    _tutor = None
    _process = None

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
                if MaxCapacitanceRoute._tutor is not None:
                    MaxCapacitanceRoute._tutor.reset()
                return {"state": "done"}
            elif task == "terminate":                
                if MaxCapacitanceRoute._process is not None:
                    MaxCapacitanceRoute._process.kill()
                    MaxCapacitanceRoute._process.join()
                EventQueue().close()
                return {"state": "done"}
            else:
                raise Exception('Unsupport parameters: ', input_data)
        except Exception as e:
            raise Exception('MaxCapacitance Manager Post error: ', str(e))

    def run():
        MaxCapacitanceRoute._process = Process(target=MaxCapacitanceRoute.tune)
        MaxCapacitanceRoute._process.start()

        return {"data": "start"}

    def tune():
        tutor = MaxCapacitanceRoute._tutor

        tc = TouchcommManager().getInstance()
        TutorWrapper = get_tutor(MaxCapacitance)
        tutor = TutorWrapper(tc)

        tutor.init()

        while True:
            t_max, t_cum_max = tutor.run()
            EventQueue().push({"state": "run", "value": {"max": int(t_max), "cum_max": int(t_cum_max)}})
