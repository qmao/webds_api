import threading
import math

from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .local_cbc import LocalCBC

g_thread = None
g_cancel = False

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
            global g_cancel
            if g_thread is not None:
                g_cancel = True
            return {"state": "done"}
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        global g_cancel
        global g_thread
        g_cancel = False
        g_thread = threading.Thread(target=LocalCBCRoute.tune, args=(params, ))
        g_thread.start()

        return {"data": "start"}

    def tune(params):
        tc = TouchcommManager().getInstance()
        tutor = LocalCBC(tc)

        generator = tutor.run(params)
        for progress in generator:
            if g_cancel:
                EventQueue().push({"state": "terminate"})
                EventQueue().close()
                return
            else:
                progress = math.floor(progress)
                EventQueue().push({"state": "run", "progress": progress})

        EventQueue().push({"state": "stop", "data": result})
        EventQueue().close()