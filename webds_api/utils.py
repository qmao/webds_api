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

        if not os.path.exists(webds.WORKSPACE_PACKRAT_CACHE_DIR):
            os.makedirs(webds.WORKSPACE_PACKRAT_CACHE_DIR, exist_ok=True)

        folder1 = webds.PACKRAT_CACHE
        folder2 = webds.WORKSPACE_PACKRAT_CACHE_DIR

        subfolders1 = set(next(os.walk(folder1))[1])
        subfolders2 = set(os.path.basename(f.path) for f in os.scandir(folder2))

        diff_subfolders1 = subfolders1.difference(subfolders2)
        diff_subfolders2 = subfolders2.difference(subfolders1)

        if diff_subfolders1:
            for subfolder in diff_subfolders1:
                cache_path = os.path.join(webds.PACKRAT_CACHE, subfolder)
                ws_path = os.path.join(webds.WORKSPACE_PACKRAT_CACHE_DIR, subfolder)
                os.symlink(cache_path, ws_path)
                print("add symlink: ", ws_path + " -> " + cache_path)
        if diff_subfolders2:
            for subfolder in diff_subfolders2:
                file_path = os.path.join(webds.WORKSPACE_PACKRAT_CACHE_DIR, subfolder)
                if os.path.islink(file_path):
                    os.unlink(file_path)
                print("delete symlink: ", file_path)
        if not diff_subfolders1 and not diff_subfolders2:
            pass

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
