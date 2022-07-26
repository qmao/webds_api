import sys
sys.path.append("/usr/local/syna/lib/python")
from touchcomm import TouchComm
from threading import Lock
from . import webds

class TouchcommManager(object):
    _instance = None
    _tc = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.connect()
        print("TouchcommManager init")

    def connect(self):
        print("Touchcomm connect()")
        ###print('Touchcomm instance:{}'.format(self))

        self._lock.acquire()
        try:
            if self._tc is not None:
                version = self._tc.comm.send_and_check("version")
            if self._tc is None or version['content'] == 'disconnect':
                self._tc = TouchComm.make(
                                protocols='report_streamer',
                                server='127.0.0.1',
                                packratCachePath=webds.WORKSPACE_PACKRAT_DIR,
                                streaming=False,
                                useAttn=False)

        except Exception as e:
            print('Touchcomm connect exception:{}'.format(e))
            self._tc = None

        finally:
            self._lock.release()
            print("Touchcomm connect() done")

    def disconnect(self):
        print("Touchcomm disconnect()")
        self._lock.acquire()
        try:
            if self._tc is not None:
                self._tc.close()
            else:
                print("already disconnected")
        except Exception as e:
            print('Touchcomm disconnect exception:{}'.format(e))
        finally:
            self._tc = None
            self._lock.release()
            print("Touchcomm disconnect() done")

    def identify(self):
        data = {}
        self._lock.acquire()
        try:
            data = self._tc.identify()
        except Exception as e:
            print('Touchcomm identify exception:{}'.format(e))
        finally:
            self._lock.release()
        return data

    def disableReport(self, id):
        data = {}
        self._lock.acquire()
        try:
            data = self._tc.disableReport(id)
        except Exception as e:
            print('Touchcomm disableReport exception:{}'.format(e))
        finally:
            self._lock.release()
        return data

    def enableReport(self, id):
        data = {}
        self._lock.acquire()
        try:
            data = self._tc.enableReport(id)
        except Exception as e:
            print('Touchcomm enableReport exception:{}'.format(e))
        finally:
            self._lock.release()
        return data

    def getReport(self, timeout=3):
        data = {}
        self._lock.acquire()
        try:
            data = self._tc.getReport(timeout)
        except Exception as e:
            print('Touchcomm getReport exception:{}'.format(e))
            raise e
        finally:
            self._lock.release()
        ### print(data)
        return data

    def getInstance(self):
        if self._tc is None:
            raise Exception("Failed to initiate ReportStreamer")
        return self._tc

    def function(self, fn, args = None):
        data = {}
        self._lock.acquire()
        try:
            if args is None:
                data = getattr(self._tc, fn)()
            else:
                data = getattr(self._tc, fn)(*args)
        except Exception as e:
            print('Touchcomm {} exception:{}'.format(fn, e))
            raise e
        finally:
            self._lock.release()
        return data

    def lock(self, lock):
        if lock:
            self._lock.acquire()
        else:
            self._lock.release()
