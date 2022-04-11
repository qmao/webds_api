from jupyter_server.base.handlers import APIHandler
import json
import re
import os
from os import listdir
from os.path import isfile, join, exists
from . import webds
from .utils import SystemHandler

from queue import Queue
import time

PT_ROOT = "/home/pi/jupyter/workspace/Synaptics/Production_Tests/"
PT_LIB_ROOT = PT_ROOT + "lib/"
PT_LIB_COMMON = PT_LIB_ROOT + "common/"
PT_WRAPPER = PT_ROOT + "wrapper/"
PT_RUN = PT_ROOT + "run/"
PT_SETS = PT_ROOT + "sets/"
PT_LIB_SCRIPT_SUBDIR = 'TestStudio/Scripts/'

g_pt_output = None

class StdoutPTHandler(Queue):
    _progress = 0
    _status = 'idle'
    _message = None

    def __init__(self):
        super().__init__()

    def write(self,msg):
        try:
            if "%" in msg:
                progress = msg[12:-1]
                self._progress = int(progress, base=10)
            sys.__stdout__.write(msg)
        except Exception as e:
            print("Oops StdoutHandler write!", e.__class__, "occurred.")
            pass

    def flush(self):
        sys.__stdout__.flush()

    def get_progress(self):
        return self._progress

    def set_progress(self, num):
        self._progress = num

    def reset(self):
        self._status = 'idle'
        self._progress = 0
        self._message = ''

    def set_status(self, status):
        self._status = status

    def get_status(self):
        return self._status

    def get_message(self):
        return self._message

    def set_message(self, message):
        self._message = message


class ProductionTestsManager():
    def __init__(self):
        super().__init__()


    def updatePyTest(src, dst):
        ###print(src)
        ###print(dst)
        try:
            with open (src, 'r' ) as f:
                content = f.read()
                newContent = re.sub('main\(\)', 'test_main()', content)

                regex = re.compile('(?<=class )\s*\w+(?=\(object\))')
                found = regex.search(content)
                className = found.group(0)
                ### print('Found: ' + className)
                ### \s*  optional spaces
                ### (?=  beginning of positive lookahead
                regex = re.compile('\w+(?=\s*=\s*' + className + ')')
                found = regex.search(content)

                testName = found.group()
                ###print('Found: ' + testName)

                asserStr = '\n        ' + 'assert ' + testName +'.result == True, \'Test failed\''
                tarStr = 'Comm2Functions.ReportProgress(100)'
                finalContent = newContent.replace(tarStr, tarStr + asserStr)

                dstFile = open(dst, "w")
                dstFile.write(finalContent)
                print('[PASS ] ', dst, " created")
        except:
            print('[ERROR] ', dst, " not created!!!!!")
            pass

    def setup(partNumber, tests):
        print("setup")

        for f in os.listdir(PT_RUN):
            if f.endswith('.py'):
                os.remove(join(PT_RUN, f))

        common, cpath = ProductionTestsManager.getCommon()
        lib, ppath = ProductionTestsManager.getChipLib(partNumber)

        for idx, val in enumerate(tests):
            pyName = 'test_{}_{}.py'.format(str(idx + 1).zfill(3), val)
            ###print(pyName)
            if val in common:
                src = join(cpath, val + '.py')
            elif val in lib:
                src = join(ppath, val + '.py')
            else:
                raise tornado.web.HTTPError(status_code=400, log_message='unknown script: {}'.format(pyName))

            dst = join(PT_RUN, pyName)
            ProductionTestsManager.updatePyTest(src, dst)

    def getScriptList(partNumber, id = None):
        tests = []
        if id is None:
            ### run all
            common, cpath = ProductionTestsManager.getCommon()
            lib, ppath = ProductionTestsManager.getChipLib(partNumber)
            tests = sorted(common) + sorted(lib)
        else:
            try:
                sets = ProductionTestsManager.getSets(partNumber)
                item = [x for x in sets if x["id"] == id]
                tests = item[0]["tests"]
            except:
                raise tornado.web.HTTPError(status_code=400, log_message='production test run {} :{} not found'.format(partNumber, id))
        return tests

    def preRun(partNumber, id = None):
        print('production test run {} :{}'.format(partNumber, id))

        tests = ProductionTestsManager.getScriptList(partNumber, id)
        ProductionTestsManager.setup(partNumber, tests)
        print(tests)
        if len(tests) is 0:
            raise tornado.web.HTTPError(status_code=400, log_message='production test {} :{} no tests'.format(partNumber, id))

    def run():
        export_wrapper = 'PYTHONPATH=' + PT_WRAPPER
        SystemHandler.CallSysCommand([export_wrapper, 'pytest', '--tb=no',  '--disable-pytest-warnings', PT_RUN])

    def getSets(partNumber):
        sets = {}
        sets_file = os.path.join(PT_SETS, partNumber + ".json")
        if exists(sets_file):
            with open(sets_file) as json_file:
                sets = json.load(json_file)
        return sets

    def getCommon():
        return [f[:-3] for f in listdir(PT_LIB_COMMON) if isfile(join(PT_LIB_COMMON, f))], PT_LIB_COMMON

    def getChipLib(partNumber):
        chip_lib = os.path.join(PT_LIB_ROOT, partNumber, PT_LIB_SCRIPT_SUBDIR)
        if not exists(chip_lib):
            raise tornado.web.HTTPError(status_code=400, log_message='production test {} lib not found'.format(partNumber))
        return [f[:-3] for f in listdir(chip_lib) if isfile(join(chip_lib, f))], chip_lib

    def getTests(partNumber):
        data = json.loads("{}")
        chip_lib = os.path.join(PT_LIB_ROOT, partNumber, "TestStudio/Scripts/")
        if not exists(chip_lib):
            return data

        chip_scripts, path = ProductionTestsManager.getChipLib(partNumber)
        print(chip_scripts)

        common_scripts, path = ProductionTestsManager.getCommon()
        print(common_scripts)

        sets = ProductionTestsManager.getSets(partNumber)

        data = {
          "common": common_scripts,
          "lib": chip_scripts,
          "sets": sets
          }
        return data

    def setTests(partNumber, data):
        sets_file = os.path.join(PT_SETS, partNumber + ".json")
        print(sets_file)
        with open(sets_file, 'w') as f:
            json.dump(data, f)
        return sets_file