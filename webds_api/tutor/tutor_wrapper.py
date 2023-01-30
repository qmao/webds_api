import threading
import sys
import time
from threading import Lock, Condition
import json
from .tutor_utils import EventQueue

class Logger(object):
    _terminate = False
    _terminal = None
    ##_log = None
    _condition = None
    
    def __init__(self, condition):
        self._terminate = False
        self._condition = condition
        
        if self._terminal is None:
            self._terminal = sys.stdout
        ###self._log = open(filename, "a")
        sys.stdout = self

    def write(self, message):
        try:
            if len(message) > 1:
                jmessage = json.loads(message)
                EventQueue().push(jmessage)

            if self._terminate:
                self.restore()
                self._condition.acquire()
                self._condition.notify()
                self._condition.release()
                sys.exit()
        except Exception as e: 
            self._terminal.write(str(e))
            pass

        self._terminal.write(message)
        ###self._log.write(message)

    def flush(self):
        self._terminal.flush()
        ##self._log.flush()

    def terminate(self):
        self._terminate = True
    
    def restore(self):
        sys.stdout = self._terminal
    

class ReturnValueThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self):
        if self._target is None:
            return  # could alternatively raise an exception, depends on the use case
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        return self.result

def get_tutor(base):
    class TutorWrapper(base):
        _logger = None
        _lock = Lock()
        _condition = Condition()

        def terminate_thread(self):
            self._lock.acquire()
            if self._logger:
                self._logger.terminate()
                self._condition.acquire()
                self._condition.wait()
                self._condition.release()
                self._logger = None
            if self._thread:
                self._thread.join()
                self._thread = None
            self._lock.release()

        def start_thread(self, f, kwargs=None):
            self._logger = Logger(self._condition)
            self._log_thread = threading.Thread(target=self.track_thread)
            self._thread = ReturnValueThread(target=f, kwargs=kwargs)
            self._thread.start()
            self._log_thread.start()

        def join_thread(self):
            if self._thread:
                return self._thread.join()
                

        def track_thread(self):
            self._thread.join()
            self._lock.acquire()
            if self._logger:
                self._logger.restore()
                self._logger = None
            self._lock.release()

    return TutorWrapper