import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import os.path
import re
import json
from ..errors import HttpBrokenPipe

class UpdateMonitor(object):
    _stamp = 0
    _filename = ""
    def __init__(self):
        self._stamp = 0
        self._filename = "/var/log/syna/update_daemon.log"

    def getStatus(self):
        ret = dict();
        ret['status'] = None
        ret['timestamp'] = -1

        if os.path.exists(self._filename):
            lstamp = os.stat(self._filename).st_mtime
            if self._stamp == lstamp:
                return ret
            self._stamp = lstamp

            for line in reversed(list(open(self._filename))):
                print(line.rstrip())
                pattern = '[@]\w+.(\w+)'
                result = re.findall(pattern, line)
                if len(result) != 0:
                    ret['status'] = result[0]
                    pattern = '(\d+:\d+:\d+/\d+/\d+:\d+:\d+:\d+.\d+)'
                    time = re.findall(pattern, line)
                    if len(time) != 0:
                        ret['timestamp'] = time[0]
                    break
        return ret

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
               ret = monitor.getStatus()
               if ret['status'] is not None:
                   send = json.dumps(ret)
                   yield self.publish(send)
               else:
                   yield tornado.gen.sleep(0.0001)

        except StreamClosedError:
            print("Stream Closed!")
            pass

        except Exception as e:
            raise HttpBrokenPipe(str(e))