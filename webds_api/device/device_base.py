

class DeviceBase(object):
    _name = ""

    def __init__(self, name):
        print("device base init")
        self._name = name
        print("device base done")

    def identify(self):
        print("identify")

    def disableReport(self, report):
        return self._tc.disableReport(report)
              
    def getAppInfo(self):
        return self._tc.getAppInfo()

    def getTouchInfo(self):
        return self._tc.getTouch()
       
    def getStaticConfig(self):
        return self._tc.getStaticConfig()
              
    def getDynamicConfig(self):
        return self._tc.getDynamicConfig()
              
    def update_dynamic_config(self, config):
        print("fixme update_dynamic_config")
    
    def update_static_config(self, config):
        print("fixme update_static_config")