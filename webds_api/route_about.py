import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from .utils import SystemHandler

def ReadPhoneInfo():
    connected=os.path.isfile('/tmp/.android.connected')
    return connected

def ReadOsInfo():
    os_info = {}
    result = SystemHandler.RunSysCommand(['cat', '/usr/lib/os-release'])
    os_list = result.split('\n')

    try:
      for element in os_list:
          name, version = element.split('=')
          os_info[name] = version

    except:
      print("something wrong")

    return os_info

def ReadSystemInfo():
    packages = [
      'report-streamer',
      'tcm2-driver',
      'libpython-touchcomm',
      'libpython-asic-programmer',
      'sprog-server']

    package_info = {}

    for i in packages:
        result = SystemHandler.RunSysCommand(['dpkg-query', '-W', i])
        name, version = result.split('\t')
        package_info[name] = version.strip()

    print(package_info)
    return package_info

class AboutHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def get(self):
        ##print(self.request.arguments)
        query = self.get_argument('query', None)

        if query == 'android-connection':
            connected = ReadPhoneInfo()
            self.finish(json.dumps({
                "connection": connected
            }))

        elif query == 'system-info':
            info = ReadSystemInfo()
            self.finish(json.dumps(info))

        elif query == 'os-info':
            info = ReadOsInfo()
            self.finish(json.dumps(info))

        else:
            data = json.loads("{}")
            self.finish(data)