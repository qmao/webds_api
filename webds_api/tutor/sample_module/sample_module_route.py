from ...touchcomm.touchcomm_manager import TouchcommManager
from .sample_module import SampleModule

class SampleModuleRoute():
    def get(handle):

        tc = TouchcommManager().getInstance()
        tutor = SampleModule(tc)

        tutor.collect()
        tutor.tune()

        print(tutor._max)
        return {"data": tutor._max}

    def post(handle, input_data):
        task = input_data["task"]

        print("Hello SampleModuleRoute post request", task)

        return {"status": "post alive"}
