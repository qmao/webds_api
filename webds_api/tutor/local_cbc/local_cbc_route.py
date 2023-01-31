import threading
import math

from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .local_cbc import LocalCBC
from ..tutor_thread import TutorThread


class LocalCBCRoute():
    _tutor = None

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
            TutorThread.terminate()
            return {"state": "done"}
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        tc = TouchcommManager().getInstance()
        LocalCBCRoute._tutor = LocalCBC(tc)

        TutorThread.register_event(LocalCBCRoute.tune_callback)
        TutorThread.start(LocalCBCRoute._tutor.run, args=(params, ))

        return {"data": "start"}

    def tune_callback(data):
        EventQueue().push({"state": "stop", "data": data})
        EventQueue().close()