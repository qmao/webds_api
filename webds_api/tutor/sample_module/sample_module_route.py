import tornado
from ...touchcomm.touchcomm_manager import TouchcommManager
from .sample_module import SampleModule
from ..tutor_thread import TutorThread
from ..tutor_utils import EventQueue

class SampleModuleRoute():
    _tutor = None

    def get(handle):
        tc = TouchcommManager().getInstance()
        tutor = SampleModule(tc)

        tutor.collect(1)
        tutor.tune()

        print(tutor._max)
        return {"data": tutor._max}

    def post(handle, input_data):
        print(input_data)

        if "count" in input_data:
            #### {"count": 500}
            count = input_data["count"]
            try:
                if SampleModuleRoute._tutor is None:
                    tc = TouchcommManager().getInstance()
                    SampleModuleRoute._tutor = SampleModule(tc)
                    TutorThread.register_event(SampleModuleRoute.tune_done)
                    TutorThread.start(SampleModuleRoute._tutor.collect, args=(count, ))

                    return {"status": "start"}
                else:
                    return {"status": "previous tutor is still alive"}
            except Exception as e:
                print(e)
                message=str(e)
                raise tornado.web.HTTPError(status_code=400, log_message=message)
        elif "action" in input_data:
            #### {"action": "terminate"}
            action = input_data["action"]
            if action == "terminate":
                TutorThread.terminate()
                SampleModuleRoute._tutor = None
                return {"status": "terminated"}
        else:
            raise tornado.web.HTTPError(status_code=400, log_message="unsupported request")

    def tune_done(data):
        SampleModuleRoute._tutor.tune()
        EventQueue().push({"data": SampleModuleRoute._tutor._max})
        EventQueue().close()
        TutorThread.register_event(None)
        SampleModuleRoute._tutor = None
