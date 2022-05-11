import os
import subprocess

class Goalkeeper():
    def CheckPrivileges(command, user = False, text=False):
        if os.geteuid() != 0 and user != True:
            command = ' '.join(command)
            command = ['su', '-c', command]

        password = subprocess.run(['echo', 'syna'], check=True, capture_output=True, text=text)
        return password

    def CallSysCommand(command, user = False):
        password = Goalkeeper.CheckPrivileges(command, user)
        subprocess.run(command, input=password.stdout)

    def CallSysCommandCapture(command, user = False):
        password = Goalkeeper.CheckPrivileges(command, user, True)
        result = subprocess.run(command, input=password.stdout, capture_output=True, text=True)
        ###print("stdout:", result.stdout, "stderr:", result.stderr)
        return result.stdout

    def CallSysCommandFulfil(command, user = False):
        if os.geteuid() != 0 and user != True:
            command =  "echo 'syna' | su -c " + "'" + command + "'"
        subprocess.check_output(command, shell=True)
