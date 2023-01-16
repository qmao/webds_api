import logging

from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .localcbc import LocalCBC

g_process = None

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
            if g_process is not None:
                g_process.kill()
                g_process.join()
                EventQueue().push({"data": "cancel"})
            EventQueue().close()
            return {"state": "done"}
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        global g_process
        g_process = Process(target=LocalCBCRoute.tune, args=(params, ))
        g_process.start()

        return {"data": "start"}

    def tune(params):
        tc = TouchcommManager().getInstance()
        tutor = LocalCBC(tc)
        result = tutor.run(params)

        EventQueue().push({"state": "stop", "data": result})