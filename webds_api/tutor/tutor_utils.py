from queue import Queue
import logging
import math


class LogHandler(logging.Handler):
    def emit(self, record):
        progress = math.floor(float(record.getMessage()))
        SSEQueue().send_event({"state": "run", "progress": progress})


class SSEQueue():
    _module = ""
    _instance = None
    _queue = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = Queue()

            logging.basicConfig(filename='example/example.log', level=logging.DEBUG)
            logging.getLogger('tuningProgress').addHandler(LogHandler())

        return cls._instance

    ##def __init__(self):
    ##    print("TestBridge init")

    def set_module_name(self, name):
        self._module = name
  
    def send_event(self, info):
        self._queue.put([self._module, info])

    def setInfo(self, name, info):
        self._queue.put([name, info])

    def getQueue(self):
        try:
            result = self._queue.get(True, 1)
        except:
            return [None, None]
        return result

    def reset(self):
        print("Queue reset")
        try:
            self._queue.queue.clear()
        except Exception as e:
            print(e)
            pass