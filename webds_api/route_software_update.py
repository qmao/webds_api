import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import re
import json

class UpdateMonitor(object):
    _stamp = 0
    _filename = ""
    def __init__(self):
        self._stamp = 0
        self.filename = "/var/log/syna/update_daemon.log"

    def getStatus(self):
        lstamp = os.stat(self.filename).st_mtime
        if self._stamp == lstamp:
            return
        self._stamp = lstamp
        print(self._stamp)

        for line in reversed(list(open(self.filename))):
            print(line.rstrip())
            pattern = '[@]\w+.(\w+)'
            result = re.findall(pattern, line)
            if len(result) != 0:
                return result[0]
        return None

class SoftwareUpdateHandler(APIHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: software-update\n')
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()

        except StreamClosedError:
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        print("software update sse")

        try:
            monitor = UpdateMonitor()
            while True:
               status = monitor.getStatus()
               if status is not None:
                   send = { "status": status }
                   send = json.dumps(send)
                   yield self.publish(send)
               else:
                   yield tornado.gen.sleep(0.0001)

        except StreamClosedError:
            print("Stream Closed!")
            pass

        except Exception as e:
            ### TypeError
            ### BrokenPipeError
            print("Oops! get report", e.__class__, "occurred.")
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)