class SampleModuleRoute():
    def get(handle):
        print("Hello SampleModuleRoute get request")

        return {"status": "get alive"}

    def post(handle, input_data):
        task = input_data["task"]

        print("Hello SampleModuleRoute post request", task)

        return {"status": "post alive"}
