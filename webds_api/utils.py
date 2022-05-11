import os
import subprocess
import re
import json
from . import webds

class SystemHandler():
    def CheckPrivileges(command, user = False, text=False):
        if os.geteuid() == 0 or user:
            print("No need to call with sudo")
        else:
            print("We're not root.")
            command = ' '.join(command)
            command = ['su', '-c', command]

        print(command)
        password = subprocess.run(['echo', 'syna'], check=True, capture_output=True, text=text)
        return password

    def CallSysCommand(command, user = False):
        password = SystemHandler.CheckPrivileges(command, user)
        subprocess.run(command, input=password.stdout)

    def RunSysCommand(command, user = False):
        password = SystemHandler.CheckPrivileges(command, user, True)
        result = subprocess.run(command, input=password.stdout, capture_output=True, text=True)
        print("stdout:", result.stdout, "stderr:", result.stderr)
        return result.stdout

    def SendSysCommand(command, user = False):
        if not user:
            command =  "echo 'syna' | su -c " + "'" + command + "'"
        print(command)
        subprocess.check_output(command, shell=True)

    def UpdateWorkSpaceCache():
        os.makedirs(webds.WORKSPACE_CACHE_DIR, exist_ok=True)

    def UpdatePackratLink():
        if os.path.exists(webds.WORKSPACE_PACKRAT_CACHE_DIR):
            try:
                print(webds.WORKSPACE_PACKRAT_CACHE_DIR)

                for f in os.listdir(webds.WORKSPACE_PACKRAT_CACHE_DIR):
                    file_path = os.path.join(webds.WORKSPACE_PACKRAT_CACHE_DIR, f)
                    if os.path.islink(file_path):
                        os.unlink(file_path)

                ### symlink has been moved to ./Packrat/Cache
                ### clean up old symlink in ./Packrat
                ### can remove these code in the future
                for f in os.listdir(webds.WORKSPACE_PACKRAT_CACHE_DIR + "/.."):
                    file_path = os.path.join(webds.WORKSPACE_PACKRAT_CACHE_DIR + "/..", f)
                    if os.path.islink(file_path):
                        os.unlink(file_path)

            except OSError as e:
                print("Error: %s - %s." % (e.filename, e.strerror))
        else:
            os.makedirs(webds.WORKSPACE_PACKRAT_CACHE_DIR, exist_ok=True)

        for packrat in os.listdir(webds.PACKRAT_CACHE):
            print(packrat)
            cache_path = os.path.join(webds.PACKRAT_CACHE, packrat)
            ws_path = os.path.join(webds.WORKSPACE_PACKRAT_CACHE_DIR, packrat)
            print(ws_path + " -> " + cache_path)
            os.symlink(cache_path, ws_path)

    def UpdateWorkspace():
        SystemHandler.CallSysCommand(['mkdir','-p', webds.PACKRAT_CACHE])
        SystemHandler.UpdatePackratLink()
        SystemHandler.UpdateWorkSpaceCache()

class HexFile():
    def GetSymbolValue(symbol, content):
          find=r'(?<='+ symbol + r'=").*(?=")'
          x = re.findall(find, content)

          if (len(x) > 0):
              return x[0]
          else:
              return None