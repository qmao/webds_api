from jupyter_server.base.handlers import APIHandler
import tornado
import json
import re
import os
from os import listdir
from os.path import isfile, join, exists
from . import webds
from .utils import SystemHandler
import threading

import time
import sys
import pytest

PT_ROOT = "/home/pi/jupyter/workspace/Synaptics/Production_Tests/"
PT_LIB_ROOT = PT_ROOT + "lib/"
PT_LIB_COMMON = PT_LIB_ROOT + "common/"
PT_WRAPPER = PT_ROOT + "wrapper/"
PT_RUN = PT_ROOT + "run/"
PT_SETS = PT_ROOT + "sets/"
PT_LIB_SCRIPT_SUBDIR = 'TestStudio/Scripts/'

sys.path.append(PT_WRAPPER)

from testBridge import TestBridge

class ProductionTestsManager():
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        print("ProductionTestsManager init")

    ##def convertPyTest(content):
    ##    newContent = re.sub('main\(\)', 'test_main()', content)
    ##    regex = re.compile('(?<=class )\s*\w+(?=\(object\))')
    ##    found = regex.search(content)
    ##    className = found.group(0)
    ##    ### print('Found: ' + className)
    ##    ### \s*  optional spaces
    ##    ### (?=  beginning of positive lookahead
    ##    regex = re.compile('\w+(?=\s*=\s*' + className + ')')
    ##    found = regex.search(content)
    ##
    ##    testName = found.group()
    ##    ###print('Found: ' + testName)
    ##
    ##    tarStr = 'Comm2Functions.ReportProgress(100)'
    ##    ### check space
    ##    space_group = re.findall(r'\n\s*(?=Comm2Functions.ReportProgress\(100\))', content)
    ##    space = space_group[-1]
    ##
    ##    assertStr = '\n' + space + 'assert ' + testName +'.result == True, \'Test failed\''
    ##    finalContent = newContent.replace(tarStr, tarStr + assertStr)
    ##
    ##    tarStr = 'XMLTestResultGenerator.XMLTestResultGenerator()'
    ##    if tarStr in finalContent and 'test.name' in finalContent:
    ##        ### check space
    ##        space_group = re.findall(r'\n(\s* |\s*\w+\s*=\s*)(?=XMLTestResultGenerator.XMLTestResultGenerator\(\))', content)
    ##        space = space_group[-1]
    ##        space = space[0: len(space) - len(space.lstrip())]
    ##
    ##        assertStr = '\n' + space +  'Comm2Functions.SetTestName(test.name)\n'
    ##        finalContent = finalContent.replace(tarStr, tarStr + assertStr)
    ##    return finalContent

    def convertPyTest(content):
        assertStr = '\n\ndef test_main():\n    main()\n    assert Comm2Functions.GetTestResult() == True, \'Test failed\''
        finalContent = content + assertStr

        tarStr = 'XMLTestResultGenerator.XMLTestResultGenerator()'
        if tarStr in finalContent and 'test.name' in finalContent:
            ### check space
            space_group = re.findall(r'\n(\s* |\s*\w+\s*=\s*)(?=XMLTestResultGenerator.XMLTestResultGenerator\(\))', finalContent)
            space = space_group[-1]
            space = space[0: len(space) - len(space.lstrip())]

            assertStr = '\n' + space +  'Comm2Functions.SetTestName(test.name)\n'
            finalContent = finalContent.replace(tarStr, tarStr + assertStr)

        return finalContent

    def updatePyTest(src, dst):
        ###print(src)
        print(dst)
        try:
            with open (src, 'r' ) as f:
                content = f.read()
                finalContent = ProductionTestsManager.convertPyTest(content)

                dstFile = open(dst, "w")
                dstFile.write(finalContent)
                print('[CREATE] ', dst, " created")
        except:
            print('[ERROR ] ', dst, " not created!!!!!")
            pass

    def setup(partNumber, tests):
        print("setup")

        for f in os.listdir(PT_RUN):
            if f.endswith('.py') and f != "conftest.py":
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
            tests = common + lib
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
        TestBridge().reset()

    def run(self):
        std_default = sys.stdout
        export_wrapper = 'PYTHONPATH=' + PT_WRAPPER
        cmd = ['--tb=no', '--disable-pytest-warnings', PT_RUN]
        pytest.main(cmd)

    def getSets(partNumber):
        sets = {}
        sets_file = os.path.join(PT_SETS, partNumber + ".json")
        if exists(sets_file):
            with open(sets_file) as json_file:
                sets = json.load(json_file)
        return sets

    def getTestList(path):
        return sorted([f[:-3] for f in listdir(path) if isfile(join(path, f))])

    def getCommon():
        return ProductionTestsManager.getTestList(PT_LIB_COMMON), PT_LIB_COMMON

    def getChipLib(partNumber):
        chip_lib = os.path.join(PT_LIB_ROOT, partNumber, PT_LIB_SCRIPT_SUBDIR)
        if not exists(chip_lib):
            raise tornado.web.HTTPError(status_code=400, log_message='production test {} lib not found'.format(partNumber))
        return ProductionTestsManager.getTestList(chip_lib), chip_lib

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
