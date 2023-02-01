import tornado
from ...touchcomm.touchcomm_manager import TouchcommManager
from .sample_module import SampleModule
from ..tutor_thread import TutorThread
from ..tutor_utils import EventQueue
from ...configuration.config_handler import ConfigHandler

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
                if TutorThread.is_alive():
                    return {"status": "previous thread is still running"}

                tc = TouchcommManager().getInstance()
                ConfigHandler.init(tc)
                SampleModuleRoute._tutor = SampleModule(tc)
                TutorThread.register_event(SampleModuleRoute.tune_done)
                TutorThread.start(SampleModuleRoute._tutor.collect, args=(count, ))

                return {"status": "start"}
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
            elif action == "commit":
                ConfigHandler.commit_config()
                return {"status": "committed"}
            elif action == "apply":
                config = SampleModuleRoute._tutor.get_configuration()
                ConfigHandler.update_static_config(config)
                return {"status": "applied"}
            elif action == "cancel":
                ConfigHandler.restore()
                return {"status": "canceled"}
        else:
            raise tornado.web.HTTPError(status_code=400, log_message="unsupported request")

    def tune_done(data):
        SampleModuleRoute._tutor.tune()
        config = SampleModuleRoute._tutor.get_configuration()
        EventQueue().push({"data": config})
        EventQueue().close()
        TutorThread.register_event(None)
