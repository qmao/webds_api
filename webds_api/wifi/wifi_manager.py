
import os
import sys
import re

sys.path.append("/home/dsdkuser/jupyter/workspace")
from wlan_helper import WlanHelper

from ..utils import SystemHandler

class WifiManager():
    def getCurrent():
        current = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-c'])

        regex = re.compile('(?<=SSID: )[A-Za-z0-9-_.\s]+')
        found = regex.search(current)

        print(found)
        if found is None:
            return None
        else:
            return found.group(0)

    def getList():
        current = WifiManager.getCurrent()
        connected = None

        wlan_list = []
        wlist = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-l'])
        param = wlist.split("\n")
        for network in param:
            token = network.split(" (")
            if len(token) == 2:
                token[1] = token[1][:-1]
                if token[0] == current:
                    connected = token
                else:
                    wlan_list.append(token)

        if connected is not None:
            wlan_list.insert(0, connected)

        data = {'status': 'on', 'list': wlan_list}
        if connected is None:
            data['connected'] = False
        else:
            data['connected'] = True

        return data

    def connect(network, password):
        WifiManager.disconnect()

        status = SystemHandler.CallSysCommandCapture(['python3', '/home/dsdkuser/jupyter/workspace/wlan_helper.py', '-s', f'"{network}"', '-p', password])
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
