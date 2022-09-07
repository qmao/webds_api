import os
import subprocess
import traceback
import re

class Goalkeeper():
    def CheckStack(command):
        slist = []
        isCallFromUtil = False
        isCallFromRoute = False
        isCallFromProductionTest = False
        for line in traceback.format_stack():
            current=line.strip()
            regex = re.compile('(?<=File \")[A-Za-z0-9-_.\s\/]+(?=\",)')
            found = regex.search(current)

            if found is not None:
                token = found.group(0)
                slist.append(token)

                if "/usr/local/lib/python3.7/dist-packages/webds_api/utils.py" in token:
                    isCallFromUtil = True
                if "/usr/local/lib/python3.7/dist-packages/webds_api/route/" in token:
                    isCallFromRoute = True
                if "/usr/local/lib/python3.7/dist-packages/webds_api/production_test/production_test_manager.py" in token:
                    isCallFromProductionTest = True

        isCallFromJupyterLab = False
        if "/usr/local/bin/jupyter-lab" in slist[0]:
            isCallFromJupyterLab = True

        if isCallFromUtil and isCallFromRoute and isCallFromJupyterLab or isCallFromProductionTest:
            return True
        else:
            print("Invalid call stack", command)
            for path in slist:
                print(path)
            return False

    def CallSysCommand(command, user = False):
        if Goalkeeper.CheckStack(command) == False:
            return
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True)
        subprocess.run(command, input=password.stdout)

    def CallSysCommandCapture(command, user = False):
        if Goalkeeper.CheckStack(command) == False:
            return ""
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True, text=True)
        result = subprocess.run(command, input=password.stdout, capture_output=True, text=True)
        return result.stdout

    def CallSysCommandFulfil(command, user = False):
        if Goalkeeper.CheckStack(command) == False:
            return
        if os.geteuid() != 0 and user != True:
            command =  "echo 'pi.x@=syna' | su -c " + "'" + command + "'"

        subprocess.check_output(command, shell=True)
