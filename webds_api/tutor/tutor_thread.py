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


class TutorThread():
    _logger = None
    _lock = Lock()
    _condition = Condition()
    _callback = None
    _thread = None

    @classmethod
    def terminate(cls):
        cls._lock.acquire()
        if cls._logger:
            cls._logger.terminate()
            cls._condition.acquire()
            cls._condition.wait()
            cls._condition.release()
            cls._logger = None
        if cls._thread:
            cls._thread.join()
            cls._thread = None
        cls._lock.release()

    @classmethod
    def start(cls, f, args=None):
        if cls._thread is not None:
            raise Exception("Sorry, previous thread is still running")
        cls._logger = Logger(cls._condition)
        cls._log_thread = threading.Thread(target=cls.track_thread)
        cls._thread = ReturnValueThread(target=f, args=args)
        cls._thread.start()
        cls._log_thread.start()

    @classmethod
    def join(cls):
        if cls._thread:
            return cls._thread.join()

    @classmethod
    def track_thread(cls):
        data = cls._thread.join()
        cls._lock.acquire()
        if cls._logger:
            cls._logger.restore()
            cls._logger = None
        if cls._callback is not None and cls._thread is not None:
            cls._callback(data)
        cls._thread = None
        cls._lock.release()

    @classmethod
    def register_event(cls, cb):
        cls._callback = cb

    @classmethod
    def is_alive(cls):
        return cls._thread is not None