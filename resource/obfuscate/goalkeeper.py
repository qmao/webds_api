import os
import subprocess

class Goalkeeper():
    def CallSysCommand(command, user = False):
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        print("QMAO CallSysCommand: ", command)
        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True)
        subprocess.run(command, input=password.stdout)

    def CallSysCommandCapture(command, user = False):
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        print("QMAO CallSysCommandCapture: ", command)
        password = subprocess.run(['echo', 'pi.x@=syna'], check=True, capture_output=True, text=True)
        result = subprocess.run(command, input=password.stdout, capture_output=True, text=True)
        return result.stdout

    def CallSysCommandFulfil(command, user = False):
        if os.geteuid() != 0 and user != True:
            command =  "echo 'pi.x@=syna' | su -c " + "'" + command + "'"

        print("QMAO CallSysCommandFulfil: ", command)
        subprocess.check_output(command, shell=True)
