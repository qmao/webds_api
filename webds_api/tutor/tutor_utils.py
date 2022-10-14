from queue import Queue
 
class SSEQueue():
    _instance = None
    _queue = Queue()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = Queue()
        return cls._instance

    ##def __init__(self):
    ##    print("TestBridge init")
  
    def setInfo(self, name, info):
        self._queue.put([name, info])

    def getQueue(self):
        try:
            result = self._queue.get(True, 3)
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