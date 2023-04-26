import os
import re
import json
from . import webds
import sys
from threading import Lock

from .obfuscate.goalkeeper import Goalkeeper

global_lock = Lock()

class SystemHandler():

    def CallSysCommand(command, user = False):
        Goalkeeper.CallSysCommand(command, user)

    def CallSysCommandCapture(command, user = False):
        return Goalkeeper.CallSysCommandCapture(command, user)

    def CallSysCommandFulfil(command, user = False):
        Goalkeeper.CallSysCommandFulfil(command, user)

    def UpdateWorkSpaceCache():
        os.makedirs(webds.WORKSPACE_CACHE_DIR, exist_ok=True)

    def UpdatePackratLink():
        global_lock.acquire()

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

        global_lock.release()

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