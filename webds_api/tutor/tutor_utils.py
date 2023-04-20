from multiprocessing import Queue
import logging
import math
import time


class ProgressHandler(logging.Handler):
    def emit(self, record):
        progress = math.floor(float(record.getMessage()))
        EventQueue().push({"state": "run", "progress": progress})

class EventQueue():
    _module = ""
    _instance = None
    _queue = None
    _alive = True
    _terminate = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = Queue()
            logging.getLogger('tuningProgress').addHandler(ProgressHandler())
        return cls._instance

    def set_module_name(self, name):
        self._module = name
  
    def push(self, info):
        self._queue.put([self._module, info])
        if self._queue.qsize() >= 2:
            time.sleep(0.05)

    def close(self):
        self._alive = False

    def pop(self):
        try:
            result = self._queue.get(True, 1)
        except:
            return [None, None]

        return result

    def is_alive(self):
        return self._alive

    def is_terminate(self):
        return self._terminate

    def terminate(self):
        self._terminate = True

    def reset(self):
        print("Queue reset")
        self._terminate = False
        try:
            while not self._queue.empty():
                self._queue.get()
            self._alive = True
        except Exception as e:
            print(e)
            pass
        ##print("Queue reset Done")