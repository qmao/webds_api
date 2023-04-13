import os
import json

class SensorMappingRoute():
    _tutor = None

    def get(handle):
        config = handle.get_argument('config', None)
        try:
            with open(os.path.join(os.path.dirname(__file__), "sensor_configurations", config + ".json"), 'r') as f:
                data = json.load(f)
                return data
        except Exception as e:
            raise Exception('Unsupport function:', __class__, __name__, str(e))

    def post(handle, input_data):
        raise Exception('Unsupport parameters: ', input_data)