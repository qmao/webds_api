from jupyter_server.base.handlers import APIHandler
import json
import re
import os
import py
import time
import sys
import pytest
import logging
import io
import threading
import tarfile


from pathlib import Path
from os import listdir
from os.path import isfile, join, exists
from queue import Queue
from TestBridge import TestBridge

from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError


PT_ROOT = '/usr/local/syna/lib/python/production_tests_v2/'
PT_LIB_ROOT = os.path.join(PT_ROOT, "lib")
PT_LIB_COMMON = os.path.join(PT_LIB_ROOT, "common")
PT_WRAPPER = os.path.join(PT_ROOT, "wrapper")
PT_RUN = os.path.join(PT_ROOT, "run")
PT_SETS = os.path.join(PT_ROOT, "sets")
PT_LIB_SCRIPT_SUBDIR = 'TestStudio/Scripts/'
PT_LOG_DIR = os.path.join(PT_RUN, "log")
PT_RESOURCE = os.path.join(PT_RUN, "resource")
PT_IMAGE_TEMP = '/tmp'
PT_TEST_PLAN_NAME = 'test_plan.json'

sys.path.append(PT_WRAPPER)

class StdoutHandler(Queue):
    _logger = None
    def __init__(self, logger):
        super().__init__()
        self._logger = logger

    def write(self, msg):
        if msg != "\n":
            self._logger.info(msg)

    def flush(self):
        sys.__stdout__.flush()

class ProductionTestsManager():
    _instance = None
    _logger = None
    _stdout = None
    _test_stdout = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ProductionTestsManager init")

    def readFile(f):
        content = {}
        if not exists(f):
            raise HttpServerError(str('file not found'))
        with open(f) as json_file:
            content = json.load(json_file)
        return content

    def importTestPlan(fpath):
        with open(os.path.join(fpath, PT_TEST_PLAN_NAME), 'rb') as f:
            content = json.load(f)
            print(content)
            partnumber = content["partnumber"]
        target = os.path.join(PT_SETS, partnumber)
        if os.path.exists(os.path.join(PT_SETS, partnumber, os.path.basename(fpath))):
            raise Exception("plan exist")
        SystemHandler.CallSysCommand(['mv', fpath, target])
        return {"partnumber" : partnumber, "plan" : os.path.basename(fpath)}

    def writeFile(f, data):
        if not exists(f):
            raise HttpServerError(str('file not found'))
 
        print("@@@@ write file", data)
        temp_file = webds.PRODUCTION_TEST_PY_TEMP
        dstFile = open(temp_file, "w")
        dstFile.write(data)
        ProductionTestsManager.__copyRootFile(temp_file, f)

    def exportPlan(partnumber, plan):
        path = os.path.join(PT_SETS, partnumber, plan)
        return ProductionTestsManager.create_tar(path, '/home/dsdkuser')

    def createPlan(partnumber, plan):
        path = os.path.join(PT_SETS, partnumber, plan)
        if os.path.exists(path):
            raise HttpServerError(str('plan exist'))
        else:
            SystemHandler.CallSysCommand(['mkdir', path])
            default = os.path.join(PT_SETS, 'template')
            SystemHandler.CallSysCommand(['cp', default + "/*", path + "/"])

            plan_file = os.path.join(path, PT_TEST_PLAN_NAME)
            with open(plan_file, 'r') as f:
                data = json.load(f)
            data['partnumber'] = partnumber

            with open(webds.WORKSPACE_TEMP_FILE, 'w') as f:
                json.dump(data, f, indent=4)

            SystemHandler.CallSysCommand(['mv', webds.WORKSPACE_TEMP_FILE, plan_file])
            return {"data": data}

        raise HttpServerError(str('case not found'))

    def deletePlan(partnumber, plan):
        path = os.path.join(PT_SETS, partnumber, plan)
        if os.path.exists(path):
            SystemHandler.CallSysCommand(['rm', path, '-rf'])

            plist = ProductionTestsManager.getPlanList(partnumber)
            return {"data": plist}
        else:
            raise HttpServerError(str('plan not found'))
        raise HttpServerError(str('case not found'))

    def setCase(partnumber, plan, data):
        path = os.path.join(PT_SETS, partnumber, plan, PT_TEST_PLAN_NAME)
        if os.path.exists(path):
            content = ProductionTestsManager.readFile(path)

            ### edit existing case
            for i, item in enumerate(content["cases"]):
                if item["name"] == data["name"]:
                    content["cases"][i] = data
                    print("@@@@@@@@ EDIT EXISTING")
                    ProductionTestsManager.writeFile(path, json.dumps(content))
                    return {"data": content}

            ### add a new case
            print("@@@@@@@@ ADD A NEW CASE")
            content["cases"].append(data)
            ProductionTestsManager.writeFile(path, json.dumps(content))
            return {"data": content}
        else:
            raise HttpServerError(str('plan not found'))

        return {}

    def deleteCase(partnumber, plan, case):
        path = os.path.join(PT_SETS, partnumber, plan, PT_TEST_PLAN_NAME)
        if os.path.exists(path):
            content = ProductionTestsManager.readFile(path)

            ### delete existing case
            for item in content["cases"]:
                print("@@@@@@@@ item", item, case)
                if item["name"] == case:
                    content["cases"].remove(item)
                    print("@@@@@@@@ DELETE EXISTING")
                    ProductionTestsManager.writeFile(path, json.dumps(content))
                    return {"data": content}
        else:
            raise HttpServerError(str('plan not found'))
        raise HttpServerError(str('case not found'))

    def getCase(partnumber, plan, case):
        path = os.path.join(PT_SETS, partnumber, plan, PT_TEST_PLAN_NAME)
        content = ProductionTestsManager.readFile(path)
        for item in content["cases"]:
            if item["name"] == case:
                return item
        return {}

    def getPlan(partnumber, plan):
        path = os.path.join(PT_SETS, partnumber, plan, PT_TEST_PLAN_NAME)
        return ProductionTestsManager.readFile(path)

    def getPlanList(partnumber):
        path = os.path.join(PT_SETS, partnumber)
        plist = sorted([f for f in listdir(path)])

        return plist

    def getPlanFolder(partnumber, plan):
        path = os.path.join(PT_SETS, partnumber, plan)
        return path

    def getScriptList(partnumber, plan):
        tests = []

        try:
            pcontent = ProductionTestsManager.getPlan(partnumber, plan)
            scripts = [c["scripts"] for c in pcontent["cases"]]
            for array in scripts:
                tests.extend(array)
                
            tests = [s["name"] for s in tests]
        except:
            raise HttpServerError('production test run {} :{} not found'.format(partnumber, id))
        print("[test scripts] ", tests)
        return tests

    def preRun(partnumber, plan):
        print('production pre run {} {} '.format(partnumber, plan))

        tests = ProductionTestsManager.getScriptList(partnumber, plan)
        ProductionTestsManager.setup(partnumber, plan, tests)
        print(tests)
        if len(tests) is 0:
            raise HttpServerError('production test {} :{} no tests'.format(partnumber, id))

    def __copyRootFile(src, dst, action = 'mv'):
        SystemHandler.CallSysCommand([ action, src, dst])
        SystemHandler.CallSysCommandFulfil('chown root:root ' + dst)
        
    def __updatePyTest(src, dst):
        temp_file = webds.PRODUCTION_TEST_PY_TEMP
        try:
            with open (src, 'r' ) as f:
                content = f.read()
                finalContent = ProductionTestsManager.convertPyTest(content)

                dstFile = open(temp_file, "w")
                dstFile.write(finalContent)
                ProductionTestsManager.__copyRootFile(temp_file, dst)
                print('[CREATE] ', dst, " created")
        except:
            print('[ERROR ] ', dst, " not created!!!!!")
            pass

    def setup(partnumber, plan, tests):
        print("setup")

        ### clean up scripts in run folder
        for f in os.listdir(PT_RUN):
            if f.endswith('.py') and f != "conftest.py":
                SystemHandler.CallSysCommand(['rm', join(PT_RUN, f)])

        ### clean up recipe files in run folder
        SystemHandler.CallSysCommand(['rm', join(PT_RUN, "*.json")])

        common, cpath = ProductionTestsManager.getCommon()
        lib, ppath = ProductionTestsManager.getChipLib(partnumber)

        ### copy scripts to run folder
        for idx, val in enumerate(tests):
            pyName = 'test_{}_{}.py'.format(str(idx + 1).zfill(3), val)
            ###print(pyName)
            if val in common:
                src = join(cpath, val + '.py')
            elif val in lib:
                src = join(ppath, val + '.py')
            else:
                raise HttpServerError('unknown script: {}'.format(pyName))
            dst = join(PT_RUN, pyName)
            ProductionTestsManager.__updatePyTest(src, dst)

        ### copy recipe to run folder
        path = os.path.join(PT_SETS, partnumber, plan)
        for fname in listdir(path):
            fpath = os.path.join(path, fname)
            ProductionTestsManager.__copyRootFile(fpath, join(PT_RUN, fname), 'cp')
            print("[COPY TO RUN] ", fpath)

        if not exists(PT_RESOURCE):
            SystemHandler.CallSysCommandFulfil('mkdir ' + PT_RESOURCE)

        ProductionTestsManager().resetLog()
        
    def getTestList(path):
        return sorted([f[:-3] for f in listdir(path) if isfile(join(path, f))])

    def getSupportedList(src):
        supported_lib = [
            "Configuration",
            "FirmwareID",
            "AbsRawCapTest",
            "AdcRangeTest",
            "DevicePackageTest",
            "ExtendedHighResistance",
            "FullRawCapTest",
            "GPIOOpen",
            "GPIOShort",
            "HighResistanceTest",
            "NoiseTest",
            "SensorSpeedTest",
            "TRxGround",
            "TRxSensorOpen",
            "TransRawCap",
            "TrxTrxShortTest",
            ###"BSCCalibration",
            "ForceButtonOpenGuardPlane",
            "ForceButtonOpenGuardTrace",
            "SyncConnectionTest",
            "SyncShortTest",
            "Attention",
            "ResetPinTest"
        ]
        tests = []
        for test in src:
            ###if test in supported_lib:
            tests.append(test)
        return tests

    def getCommon():
        return ProductionTestsManager.getSupportedList(ProductionTestsManager.getTestList(PT_LIB_COMMON)), PT_LIB_COMMON

    def getChipLib(partnumber):
        chip_lib = os.path.join(PT_LIB_ROOT, partnumber, PT_LIB_SCRIPT_SUBDIR)
        if not exists(chip_lib):
            raise HttpServerError('production test {} lib not found'.format(partnumber))
        return ProductionTestsManager.getSupportedList(ProductionTestsManager.getTestList(chip_lib)), chip_lib

    def getLib(partnumber):
        data = json.loads("{}")
        chip_lib = os.path.join(PT_LIB_ROOT, partnumber, "TestStudio/Scripts/")
        if not exists(chip_lib):
            raise HttpServerError('production test {} not found'.format(chip_lib))

        chip_scripts, path = ProductionTestsManager.getChipLib(partnumber)
        common_scripts, path = ProductionTestsManager.getCommon()

        data = {
          "common": common_scripts,
          "lib": chip_scripts
          }

        print(data)
        return data
        
    def convertPyTest(content):
        try:
            regex = re.compile('(?<=metadata name=\")(\w+([-]?)([\s*]?))+')
            test = regex.search(content)

            if "from Comm2Functions import *" in content:
                namespace = ""
            else:
                namespace = "Comm2Functions."

            assertStr = '\n\ndef test_main():\n    ' + namespace + 'Init("' + test.group() + '")\n    main()\n    assert Comm2Functions.GetTestResult() == True, \'Test failed\''
        except:
            assertStr = '\n\ndef test_main():\n    ' + namespace + 'Init("")\n    main()\n    assert Comm2Functions.GetTestResult() == True, \'Test failed\''
        finalContent = content + assertStr
        finalContent = finalContent.replace("\\\\TestStudio\\\\", "/run/")

        return finalContent

    def resetLog(self):
        name='ProductionTests'
        log_temp = webds.PRODUCTION_TEST_LOG_TEMP

        logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
        rootLogger = logging.getLogger()

        fileHandler = logging.FileHandler(log_temp)
        fileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(fileHandler)

        self._logger = rootLogger

        self._test_stdout = StdoutHandler(self._logger)
        self._stdout = sys.stdout
        sys.stdout = self._test_stdout
        sys.stdout.isatty = lambda: False
        
    def run(self):
        TestBridge().reset()
        export_wrapper = 'PYTHONPATH=' + PT_WRAPPER
        cmd = ['--tb=no', '--disable-pytest-warnings', '-s', '--disable-warnings', PT_RUN]

        pytest.main(cmd)

        ProductionTestsManager().updateLog()
        
    def updateLog(self):
        sys.stdout = self._stdout
        log_temp = webds.PRODUCTION_TEST_LOG_TEMP
        SystemHandler.CallSysCommand(['mkdir','-p', PT_LOG_DIR])
        SystemHandler.CallSysCommand(['mv', log_temp, webds.PRODUCTION_TEST_LOG_FILE])

    def checkTestBridge(self):
        report = TestBridge().getQueue()
        index = name = status = outcome = None
        if report is None:
            name = None
        else:
            nodeid = report[0]
            status = report[1]
            outcome = report[2]
            if status != 'finished':
                regex = re.compile('\w+(?=\.py)')
                found = regex.search(nodeid)
                name = found.group(0)

                regex = re.compile('(?<=_)\w+(?=\_)')
                found = regex.search(name)
                index = found.group(0)

        return index, name, status, outcome
