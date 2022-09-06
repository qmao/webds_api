import os
import subprocess
import traceback
import re

class Goalkeeper():
    def CheckStack():
        slist = []
        for line in traceback.format_stack():
            current=line.strip()
            regex = re.compile('(?<=File \")[A-Za-z0-9-_.\s\/]+(?=\",)')
            found = regex.search(current)

            if found is not None:
                slist.append(found.group(0))

        isCallFromJupyterLab = False
        if "/usr/local/bin/jupyter-lab" in slist[0]:
            isCallFromJupyterLab = True

        slist.reverse()

        isCallFromUtil = False
        if slist[2] == "/usr/local/lib/python3.7/dist-packages/webds_api/utils.py":
            isCallFromUtil = True

        isCallFromRoute = False
        regex = re.compile('^/usr/local/lib/python3.7/dist-packages/webds_api/route/')
        found = regex.search(slist[3])

        if found is not None:
            isCallFromRoute = True

        if isCallFromUtil and isCallFromRoute and isCallFromJupyterLab:
            return True
        else:
            print("Invalid call stack")
            for path in slist:
                print(path)
            return False

    def CallSysCommand(command, user = False):
        if Goalkeeper.CheckStack() == False:
            return
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True)
        subprocess.run(command, input=password.stdout)

    def CallSysCommandCapture(command, user = False):
        if Goalkeeper.CheckStack() == False:
            return ""
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True, text=True)
        result = subprocess.run(command, input=password.stdout, capture_output=True, text=True)
        return result.stdout

    def CallSysCommandFulfil(command, user = False):
        if Goalkeeper.CheckStack() == False:
            return
        if os.geteuid() != 0 and user != True:
            command =  "echo 'pi.x@=syna' | su -c " + "'" + command + "'"

        subprocess.check_output(command, shell=True)
