import threading
import math

from multiprocessing import Process
from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .local_cbc import LocalCBC
from ..tutor_wrapper import *


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
            LocalCBCRoute._tutor.terminate_thread()
            return {"state": "done"}
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        thread = threading.Thread(target=LocalCBCRoute.tune, args=(params, ))
        thread.start()

        return {"data": "start"}

    def tune(params):
        tc = TouchcommManager().getInstance()
        TutorWrapper = get_tutor(LocalCBC)
        LocalCBCRoute._tutor = TutorWrapper(tc)

        LocalCBCRoute._tutor.start_thread(LocalCBCRoute._tutor.run, args=(params, ))
        result = LocalCBCRoute._tutor.join_thread()

        EventQueue().push({"state": "stop", "data": result})
        EventQueue().close()