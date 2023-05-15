
from ...touchcomm.touchcomm_manager import TouchcommManager
from .hybrid_analog import HybridAnalog
from ..tutor_utils import EventQueue
from ...configuration.config_handler import ConfigHandler
from ..tutor_thread import TutorThread

class HybridAnalogRoute():
    _tutor = None

    def get(handle):
        return HybridAnalogRoute.currentSetting()
        
    def post(handle, input_data):
        task = input_data["task"]

        if task == None:
            raise Exception('Unsupport input parameters: ', input_data)
        if task == "run":
            marginHybridAnalogADC = input_data["settings"]
            return HybridAnalogRoute.run(marginHybridAnalogADC)
        elif task == "getSetting":
            return HybridAnalogRoute.currentSetting()
        elif task == "getAdcRange":
            return HybridAnalogRoute.getADCRange()
        elif task == "terminate":
            TutorThread.terminate()
            return {"state": "done"}
        else:
            raise Exception('Unsupport parameters: ', input_data)

    def run(params):
        tc = TouchcommManager().getInstance()
        h = HybridAnalog(tc)
        
        TutorThread.register_event(HybridAnalogRoute.tune_callback)
        TutorThread.start(h.run, args=(params, ))
        return 

    def tune_callback(data):
        EventQueue().push({"state": "run", "data": data})
        EventQueue().push({"state":"run", "progress":100})
        EventQueue().close()

    def currentSetting():
        tc = TouchcommManager().getInstance()
        h = HybridAnalog(tc)
        ret = h.beforeTuning()
        print(ret[0],ret[1])
        return {"x":ret[0], "y":ret[1]}

    def getADCRange():
        tc = TouchcommManager().getInstance()
        h = HybridAnalog(tc)
        ret = h.getADCRange()
        print(ret)
        return ret
