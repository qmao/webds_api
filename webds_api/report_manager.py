import sys
sys.path.append("/usr/local/syna/lib/python")
import threading
import time
from .touchcomm_manager import TouchcommManager
from threading import Thread
from threading import Lock
from time import sleep
    

class ReportManager(object):
    _instance = None
    _counter = 0
    _thread = None
    _report = ('timeout', None)
    _frame_count = 1
    _state = 'stop'
    ###_lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ReportManager singleton object is created")


    def doit(self, arg):
        t = threading.currentThread()
        tc = None
        try:
            tc = TouchcommManager()
            while getattr(t, "do_run", True):
                if self._state == 'pause':
                    sleep(0.1)
                    continue
                ###self._lock.acquire()
                self._report = tc.getReport(1)
                if self._report != ('timeout', None):
                    self._frame_count += 1
                ###self._lock.release()
                sleep(0.0001)
                ###print ("working on %s" % self._counter)
            self.reset()
            print("Stopping as you wish.")
        except Exception as e:
            print(tc)
            if tc is not None:
                print("report sse disconnect tc")
                tc.disconnect()
            raise

    def reset(self):
        self._report = ('timeout', None)
        self._frame_count = 1
        self._state = 'stop'

    def getReport(self):
        ###self._lock.acquire()
        data = self._report
        ###self._lock.release()
        return data, self._frame_count
            
    def setState(self, state):
        print("Set state:", state)
        self._state = state
        if self._state is 'start':
            if self._counter is 0:
                print("Create Report Thread")
                self._thread = threading.Thread(target=self.doit, args=("task",))
                self._thread.start()
            self._counter += 1
        elif self._state is 'stop':
            if self._counter > 0:
                self._counter -= 1
                if self._counter is 0:
                    self._thread.do_run = False