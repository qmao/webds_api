import time

import numpy as np

from ..tutor_thread import TutorThread
from ..tutor_utils import EventQueue
from .accutune_v5 import pdnr_tool


def convertToJSONSerializable(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return convertToJSONSerializable(obj.tolist())
    elif isinstance(obj, (list, tuple)):
        return [convertToJSONSerializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convertToJSONSerializable(v) for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        return convertToJSONSerializable(obj.__dict__)
    else:
        return obj


class PDNRRoute():
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

        if PDNRRoute._tutor is None:
            PDNRRoute._tutor = pdnr_tool

        if request == None:
            raise Exception("No request specified: ", input_data)

        if request == "cancel":
            TutorThread.terminate()
            return None

        retval = None
        try:
            tutor_function = getattr(PDNRRoute._tutor, request)
            if request == "tuneData" or request == "selectData":
                TutorThread.register_event(PDNRRoute._thread_completed)
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

        return convertToJSONSerializable(retval)
