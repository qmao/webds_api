import sys
sys.path.append("/usr/local/syna/lib/python")
from programmer import AsicProgrammer
from .touchcomm_manager import TouchcommManager

class ProgrammerManager(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ProgrammerManager singleton object is created")

    def program(filename):
        ### disconnect tcm if exist
        try:
            tc = TouchcommManager()
            tc.disconnect()
        except:
            print("tcm not exist")
            pass

        tc.lock(True)
        try:
            AsicProgrammer.programHexFile(filename, communication='socket', server='127.0.0.1')
        finally:
            tc.lock(False)