import time

from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_thread import TutorThread
from ..tutor_utils import EventQueue
from .int_dur import IntDurTuner


class IntDurRoute():
    _tutor = None
    _cancel = False

    def _thread_completed(data):
        time.sleep(0.5)
        EventQueue().push({"state": "completed"})
        EventQueue().close()
        TutorThread.register_event(None)

    def post(handle, input_data):
        request = input_data["request"]
        args = None
        if "arguments" in input_data:
            args = input_data["arguments"]

        if IntDurRoute._tutor is None:
            tc = TouchcommManager().getInstance()
            IntDurRoute._tutor = IntDurTuner(tc)

        if request == None:
            raise Exception("No request specified: ", input_data)

        if request == "cancel":
            TutorThread.terminate()
            return None

        retval = None
        try:
            tutor_function = getattr(IntDurRoute._tutor, request)
            if "collect" in request:
                TutorThread.register_event(IntDurRoute._thread_completed)
                if args is None:
                    TutorThread.start(tutor_function, args=())
                else:
                    TutorThread.start(tutor_function, args=args)
            else:
                if args is None:
                    retval = tutor_function()
                else:
                    retval = tutor_function(*args)
        except Exception as e:
            raise Exception("Error executing {}: ".format(request), str(e))

        return retval
