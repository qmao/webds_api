import pytest
from queue import Queue

 
class TestBridge():
    _instance = None
    _event = None
    _queue = Queue()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = Queue()
        return cls._instance

    ##def __init__(self):
    ##    print("TestBridge init")
        
    def setTestResult(self, nodeid, state, result):
        self._queue.put([nodeid, state, result])
        
    def getQueue(self):
        try:
            result = self._queue.get(True, 1)
        except:
            return None
        return result
        
    def reset(self):
        self._queue.queue.clear()
        print("TestBridge reset")