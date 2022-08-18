import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
import subprocess

from . import webds
from .utils import SystemHandler
from .touchcomm_manager import TouchcommManager
from os.path import exists

from .wifi.wifi_manager import WifiManager

class ConnectionSettings:
    @staticmethod
    def getValue(key):
        with open(webds.CONNECTION_SETTINGS_FILE) as json_file:
            data = json.load(json_file)
            # Print the data of dictionary
            if key in data:
                print(key, ":", data[key])
                return data[key]
            else:
                print(key, " value not found")
                return json.loads("{}")

    @staticmethod
    def setValue(key, value):
        with open(webds.CONNECTION_SETTINGS_FILE) as json_file:
            data = json.load(json_file)

        if key in data:
            print(key, " found")
        else:
            print("key not found. create new")

        data[key] = value
        ConnectionSettings.updateConnectionJsonFile(data)

    @staticmethod
    def deleteObject(obj):
        with open(webds.CONNECTION_SETTINGS_FILE) as json_file:
            data = json.load(json_file)
        if obj in data:
            del data[obj]
            ConnectionSettings.updateConnectionJsonFile(data)
        else:
            print(obj, " not exist");

    @staticmethod
    def updateConnectionJsonFile(data):
        with open(webds.CONNECTION_SETTINGS_FILE_TEMP, 'w') as json_file:
            json.dump(data, json_file, indent=4)
        SystemHandler.CallSysCommand(['chmod', '644', webds.CONNECTION_SETTINGS_FILE_TEMP])
        SystemHandler.CallSysCommand(['chown', 'root:root', webds.CONNECTION_SETTINGS_FILE_TEMP])
        SystemHandler.CallSysCommand(['mv', webds.CONNECTION_SETTINGS_FILE_TEMP, webds.CONNECTION_SETTINGS_FILE])


class SettingsHandler(APIHandler):
    @tornado.web.authenticated
    def get(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)
        print(subpath)
        print(self.request.arguments)
        query = self.get_argument('query', None)
        print(query)

        data = json.loads("{}")

        paths = subpath.split("/")
        if len(paths) < 1:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")

        if paths[0] == 'connection':
            ### check json file exists
            if not exists(webds.CONNECTION_SETTINGS_FILE):
                error = str(webds.CONNECTION_SETTINGS_FILE) +  ' not found'
                print(error)
                message=str(error)
                raise tornado.web.HTTPError(status_code=400, log_message=message)

            argument = self.get_argument('query', None)
            print(argument)
            if argument == 'default':
                data = ConnectionSettings.getValue('default')
            if argument == 'custom':
                data = ConnectionSettings.getValue('custom')

        elif paths[0] == 'wifi':
            print("get wifi list")
            data = {'status': 'on', 'list': "1111", 'current': "2222"}
            wlist = WifiManager.getList()
            print(wlist)

        else:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")

        self.finish(data)

    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        data = json.loads("{}")

        if subpath == 'connection':
            ### check json file exists
            if not exists(webds.CONNECTION_SETTINGS_FILE):
                error = str(webds.CONNECTION_SETTINGS_FILE) +  'not found'
                print(error)
                message=str(error)
                raise tornado.web.HTTPError(status_code=400, log_message=message)

            input_data = self.get_json_body()
            print(input_data)

            action = input_data["action"]
            print(action)
            if action == "reset":
                ConnectionSettings.deleteObject('custom')
            elif action == "update":
                ConnectionSettings.setValue('custom', input_data["value"])

                ### touchcomm use new settings
                try:
                    tc = TouchcommManager()
                    tc.disconnect()
                    tc.connect()
                    obj = tc.getInstance()

                    protocol = obj.comm.get_interface()
                    data["interface"] = protocol
                    if protocol == "i2c":
                        data["i2cAddr"] = obj.comm.i2cAddr
                        data["speed"] = obj.comm.speed
                    elif protocol == "spi":
                        data["spiMode"] = obj.comm.spiMode
                        data["speed"] = obj.comm.speed

                    data["useAttn"] = obj.comm.useAttn
                    data["vdd"] = obj.comm.vdd
                    data["vddtx"] = obj.comm.vddtx
                    data["vled"] = obj.comm.vled
                    data["vpu"] = obj.comm.vpu
                    data["streaming"] = obj.comm.streaming

                    print(data)
                except Exception as error:
                    print(error)
                    message=str(error)
                    raise tornado.web.HTTPError(status_code=400, log_message=message)

        elif subpath == 'wifi':
            input_data = self.get_json_body()
            print(input_data)
            if "status" in input_data:
                print(input_data["status"])
                data = {"status": "done"}

            elif "action" in input_data:
                if input_data["action"] == 'connect':
                    if "network" in input_data and "password" in input_data:
                        status = WifiManager.connect(input_data["network"], input_data["password"])
                        data = {"status": status}
                    else:
                        raise tornado.web.HTTPError(status_code=405, log_message="network and password not in json body")
                elif input_data["action"] == 'disconnect':
                    print("disconnect")
                    data = {"status": "done"}

                else:
                    raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
            else:
                raise tornado.web.HTTPError(status_code=405, log_message="Not implement")

        elif subpath == 'adb':
            input_data = self.get_json_body()
            print(input_data)
            if "ip" in input_data and "connect-port" in input_data and "pair-port" in input_data and "pair-code" in input_data:
                pair_code = input_data["pair-code"]
                ### echo $3 | adb pair $2
                ### adb connect $1
                pair_ip = input_data["ip"] + ":" + input_data["pair-port"]
                connect_ip = input_data["ip"] + ":" + input_data["connect-port"]

                ### try to connect directly
                result = SystemHandler.CallSysCommandCapture(['adb', 'connect', connect_ip])
                if "connected" in result:
                     data = {"connect": True, "pair": None}
                     self.finish(data)
                     return

                ### [PASS] (returncode=0, stdout='Enter pairing code: Successfully paired to xxx.xxx.xxx.xxx:xxxxx [guid=adb-R3CR1099MNB-KOcNXW]\n', stderr='')
                ### [FAIL] (returncode=0, stdout='Enter pairing code: Failed: Unable to start pairing client.\n', stderr=''
                password = subprocess.run(['echo', pair_code ], check=True, capture_output=True, text=True)
                result = subprocess.run(['adb', 'pair', pair_ip], input=password.stdout, capture_output=True, text=True)
                print(result.stdout)
                if "Failed"  in result.stdout:
                    data = {"connect": False, "pair": False}
                    self.finish(data)
                    return

                ### [PASS] connected to xxx.xxx.xxx.xxx:xxxxx
                ### [FAIL] failed to connect to xxx.xxx.xxx.xxx:xxxxx
                result = SystemHandler.CallSysCommandCapture(['adb', 'connect', connect_ip])
                if "failed" in result:
                     data = {"connect": False, "pair": True}
                     self.finish(data)
                     return

                data = {"connect": True, "pair": True}
                self.finish(data)
                return

            else:
                raise tornado.web.HTTPError(status_code=405, log_message="Invalid input params for adb connect")

        else:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")

        self.finish(data)
