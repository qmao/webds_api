import os
import sys
import re

from ..utils import SystemHandler

from .. import webds

class WifiManager():
    def getMode():
        current = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '-c'])

        regex = re.compile('(?<=Mode: )[A-Za-z0-9-_.\s]+(?= \()')
        found = regex.search(current)

        print(current)
        print(found)
        if found is None:
            return None
        else:
            return found.group(0)

    def getConnectedSSID():
        current = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '-c'])

        regex = re.compile('(?<=SSID: )[A-Za-z0-9-_.\s]+(?= \()')
        found = regex.search(current)

        ##regex = re.compile('(?<=Mode: )[A-Za-z0-9-_.]+')
        ##found = regex.search(current)

        print(found)
        if found is None:
            return None
        else:
            return found.group(0)

    def setSTA():
        ret = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '--sta'])
        print(ret)
        return ret

    def setAP():
        ret = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '--ap'])
        print(ret)
        return ret

    def getList():
        current = WifiManager.getConnectedSSID()
        connected = None

        wlan_list = []
        wlist = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '-l'])
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
        ###WifiManager.disconnect()

        status = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '-s', f'"{network}"', '-p', password])
        print(status)
        regex = re.compile('(?<=status: )\w+')
        found = regex.search(status)

        if found is None:
            return False
        elif found.group(0) == 'FAIL':
            return False
        return True

    def disconnect():
        status = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '-d'])
        print(status)

    def turnOn():
        status = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '--on'])
        print(status)

    def turnOff():
        status = SystemHandler.CallSysCommandCapture(['python3', webds.WIFI_HELPER_PY, '--off'])
        print(status)