import json

from ...touchcomm.touchcomm_manager import TouchcommManager
from ..tutor_thread import TutorThread
from ..tutor_utils import EventQueue
from .frame_timing import FrameTiming

class FrameTimingRoute():
    _tutor = None

    def _thread_completed(data):
        EventQueue().close()
        TutorThread.register_event(None)

    def post(handle, input_data):
        fn = input_data["function"]
        args = None
        if "arguments" in input_data:
            args = input_data["arguments"]
        
        if FrameTimingRoute._tutor is None:
            tc = TouchcommManager().getInstance()
            FrameTimingRoute._tutor = FrameTiming(tc)

        retval = None
        try:
            tutor_function = getattr(FrameTimingRoute._tutor, fn)
            if any([x in fn for x in []]):
                TutorThread.register_event(FrameTimingRoute._thread_completed)
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
            print("FrameTiming Exception ({}): {}".format(fn, e))
            raise e

        return retval