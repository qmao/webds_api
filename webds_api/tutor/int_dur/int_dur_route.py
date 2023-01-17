import inspect
import math
import threading
import time

from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_utils import EventQueue
from .int_dur import IntDurTuner


class IntDurRoute():
    _tutor = None
    _cancel = False

    def _run_generator_thread(tutor_function, args):
        try:
            if args is None:
                generator = tutor_function()
            else:
                generator = tutor_function(*args)

            for progress in generator:
                if IntDurRoute._cancel:
                    EventQueue().push({"state": "terminated"})
                    EventQueue().close()
                    return
                else:
                    progress = math.floor(progress * 100)
                    EventQueue().push({"state": "running", "progress": progress})

            time.sleep(0.5)
            EventQueue().push({"state": "completed"})
        except:
            EventQueue().push({"state": "terminated"})
        finally:
            EventQueue().close()

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
            IntDurRoute._cancel = True
            return None

        retval = None
        try:
            tutor_function = getattr(IntDurRoute._tutor, request)
            if inspect.isgeneratorfunction(tutor_function):
                IntDurRoute._cancel = False
                thread = threading.Thread(target=IntDurRoute._run_generator_thread, args=(tutor_function, args))
                thread.start()
            else:
                if args is None:
                    retval = tutor_function()
                else:
                    retval = tutor_function(*args)
        except Exception as e:
            raise Exception("Error executing {}: ".format(request), str(e))

        return retval
