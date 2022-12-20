
from device_base import DeviceBase
from device_route import DeviceRoute

class Runtime(object):
    _instance = None
    _callback = None

    def __init__(self, name, callback):
        print("device init", name)

        self._callback = callback
        if name == "route":
            self._instance = DeviceRoute(name)
        else:
            self._instance = DeviceBase(name)
        print("device done")
        
    def identify(self):
        return self._instance.identify()
        
    def disableReport(self, report):
        return self._instance.disableReport(report)
    
    def enableReport(self, report):
        return self._instance.enableReport(report)
              
    def getAppInfo(self):
        return self._instance.getAppInfo()

    def getTouchInfo(self):
        return self._instance.getTouchInfo()
       
    def getStaticConfig(self):
        return self._instance.getStaticConfig()
              
    def getDynamicConfig(self):
        return self._instance.getDynamicConfig()
              
    def update_dynamic_config(self, config):
        return self._instance.update_dynamic_config(config)
    
    def update_static_config(self, config):
        return self._instance.update_static_config(config)
    
    def getReport(self):
        return self._instance.getReport()
    
    def sendEvent(self, module, event):
        self._callback(module, event)
        ###self._instance.sendEvent(module, event)

    
    