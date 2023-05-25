import tornado
from jupyter_server.base.handlers import APIHandler
import os
import re
import json
from ..utils import SystemHandler

def ReadPhoneInfo():
    connected=os.path.isfile('/tmp/.android.connected')
    return connected

def ReadOsInfo():
    os_info = {}
    result = SystemHandler.CallSysCommandCapture(['cat', '/usr/lib/os-release'])
    os_list = result.split('\n')

    try:
      for element in os_list:
          if element != "":
              name, version = element.split('=')
              os_info[name] = version
    except:
      print("something wrong")

    return os_info

def ReadSystemInfo():
    packages = [
      'gpio-tool',
      'jupyterlab',
      'libpython-asic-programmer',
      'libpython-touchcomm',
      'pinormos-base',
      'pinormos-dsdk-rev',
      'pinormos-eep',
      'power-dac8574',
      'report-streamer',
      'sprog-server',
      'streamer-router',
      'tcm2-driver',
      'updatedaemon',
      'webds',
      'wlan-manager']

    package_info = {}

    for i in packages:
        result = SystemHandler.CallSysCommandCapture(['dpkg-query', '-W', i])
        try:
            name, version = result.split('\t')
            package_info[name] = version.strip()
        except:
            pass

    print(package_info)
    return package_info

def read_cpu_info():
    cpu_info = {}
    result = SystemHandler.CallSysCommandCapture(["cat", "/proc/cpuinfo"])
    info = result.split("\n")

    try:
        processor = ""
        for element in info:
            if element == "":
                processor = ""
                continue
            key, val = re.split("\t*: ", element)
            if key == "processor":
                processor = key + " " + val
                cpu_info[processor] = {}
            elif processor != "":
                cpu_info[processor][key] = val
            else:
                cpu_info[key] = val
    except:
      print("something wrong")

    return cpu_info

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

        elif query == 'cpu-info':
            info = read_cpu_info()
            self.finish(json.dumps(info))

        else:
            data = json.loads("{}")
            self.finish(data)
