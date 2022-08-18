
import os
import sys
import re

sys.path.append("/home/dsdkuser/jupyter/workspace")
from wlan_helper import WlanHelper

from ..utils import SystemHandler

class WifiManager():
    def getCurrent():
        current = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-c'])

        regex = re.compile('(?<=SSID: )\w+')
        found = regex.search(current)

        if found is None:
            return None
        else:
            return found.group(0)

    def getList():
        current = WifiManager.current()
        connected = None

        wlan_list = []
        wlist = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-l'])
        param = wlist.split("\n")
        for network in param:
            token = network.split(" ")
            if len(token) == 2:
                if token[0] == current:
                    connected = token
                else:
                    wlan_list.append(token)

        if connected is not None:
            wlan_list.insert(0, connected)

        print(wlan_list)

    def connect(network, password):
        WifiManager.disconnect()

        status = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-s', network, '-p', password])
        print(status)
        regex = re.compile('(?<=status: )\w+')
        found = regex.search(status)

        if found is None:
            return False
        elif found.group(0) == 'FAIL':
            return False
        return True

    def disconnect():
        status = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-d'])
        print(status)
