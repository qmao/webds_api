
from device_base import DeviceBase

import sys
sys.path.append('/usr/local/lib/python3.7/dist-packages/webds_api/touchcomm')
sys.path.append('/usr/local/lib/python3.7/dist-packages/webds_api/configuration')
sys.path.append('/usr/local/lib/python3.7/dist-packages/webds_api/tutor')

from touchcomm_manager import TouchcommManager
from config_handler import ConfigHandler
from tutor_utils import SSEQueue

class DeviceRoute(DeviceBase):
    _tc = None
    _config = None
    _queue = None
        
    def __init__(self, name):
        print("device route init")
        self._name = name
        print("device route done")

        self._tc = TouchcommManager()
        self._config = ConfigHandler(self._tc)
        self._queue = SSEQueue()
        
    def identify(self):
        return self._tc.identify()
              
    def disableReport(self, report):
        return self._tc.disableReport(report)
    
    def enableReport(self, report):
        return self._tc.enableReport(report)
              
    def getAppInfo(self):
        return self._config.getAppInfo()

    def getTouchInfo(self):
        return self._config.getTouchInfo()
       
    def getStaticConfig(self):
        return self._config.getStaticConfig()
              
    def getDynamicConfig(self):
        return self._config.getDynamicConfig()
              
    def update_dynamic_config(self, config):
        self._config.update_dynamic_config(config)
        
    def update_static_config(self, config):
        self._config.update_static_config(config)
        
    def getReport(self):
        report = self._tc.getReport()
        return report
    
    def sendEvent(self, module, event):
        print("---- [EVENT]", module, event)
        ##self._queue.setInfo(module, event)