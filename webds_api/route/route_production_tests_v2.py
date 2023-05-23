import tornado
from tornado.iostream import StreamClosedError
from tornado import gen
from jupyter_server.base.handlers import APIHandler
import os
from os import listdir
import json
import threading
import time
from ..production_test_v2.production_test_manager import ProductionTestsManager
from ..errors import HttpStreamClosed, HttpServerError
from ..file.file_manager import FileManager
import tarfile
from io import BytesIO
from .. import webds
from ..utils import SystemHandler
from ..production_test_v2.production_test_result import TestResult

g_production_test_thread = None
g_production_test_log_id = 123456

class ProductionTestsV2Handler(APIHandler):
    
    def split_path(path):
        parts = []
        if path == '':
            return parts
        while path != '/':
            path, part = os.path.split(path)
            parts.append(part)

        parts.append(path)
        parts.reverse()
        return parts
    
    def get_params(path):
        params = {'task': None, 'target': None}
        p = ProductionTestsV2Handler.split_path(path)

        ##['/', 'partnumber', 'partnumberA', 'planA', 'caseA']
        plen = len(p)
        params["level"] = plen
        if plen >= 2:
            params["target"] = p[1]
            if plen >= 3:
                params["partnumber"] = p[2]
                params["target"] = "lib"
                if plen >= 4:
                    params["plan"] = p[3]
                    params["target"] = "plan"
                    if plen >= 5:
                        params["case"] = p[4]
                        params["target"] = "case"

        print(params)
        return params

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: production-tests\n')
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()

        except StreamClosedError:
            print("stream close error!!")
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)
        print("subpath:", subpath)
        ###print(cluster_id)
        
        try:
            query = self.get_query_argument("query")
        except:
            query = None

        print("query:", query)
        print("arguments:", self.request.arguments)

        data = json.loads("{}")

        params = ProductionTestsV2Handler.get_params(subpath)
        ###test_results = TestResult(g_production_test_log_id)

        if params["target"] is None:
            print("SSE LOOP!!!")
            data = json.loads("{}")
            ### GET/SSE
            pt = ProductionTestsManager()
            while True:
                try:
                    index, name, status, outcome = pt.checkTestBridge()
                    if name is not None:
                        if status == 'started':
                            send = {
                                "index" : index,
                                "name" :  name,
                                "status" : status
                            }
                            time.sleep(0.3)
                            yield self.publish(json.dumps(send))
                        elif status == 'done':
                            send = {
                                "index" : index,
                                "name"  :  name,
                                "status" : status,
                                ###"result" : outcome
                                "result" : 'pass'
                            }
                            ###test_results.add_result(send)
                            yield self.publish(json.dumps(send))
                        else:
                            print("unknown status: ", )
                    else:
                        if status == 'finished':
                            print("[TEST FINISHED]")
                            self.set_header('content-type', 'text/event-stream')
                            self.write('id: finished\n')
                            self.write('data: {}\n\n')
                            self.finish(json.dumps({
                                "status" : "finished"
                            }))
                            break
                    yield gen.sleep(0.0001)
    
                except StreamClosedError:
                    pt.stopTests()
                    raise HttpStreamClosed()
                ###finally:
                ###    test_results.save_results_to_json('/home/dsdkuser/test.log')

        elif params["target"] == 'log':
            print("GET LOG")
        else:
            partNumber = params["partnumber"]
            print(partNumber)

            if params["target"] == "lib":
                if query == 'lib':
                    data = ProductionTestsManager.getLib(partNumber)
                elif query == 'plans':
                    ProductionTestsV2Handler.check_import_folder()
                    plans = ProductionTestsManager.getPlanList(partNumber)
                    data = { 'plans': plans }
                else:
                    print("ERROR HANDLING")

            elif params["target"] == "plan":
                print("get_plan")
                data = ProductionTestsManager.getPlan(partNumber, params["plan"])

            elif params["target"] == "case":
                print("get_case")
                data = ProductionTestsManager.getCase(partNumber, params["plan"], params["case"])

            self.finish(data)
    
    @tornado.web.authenticated
    async def post(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        params = ProductionTestsV2Handler.get_params(subpath)

        if params["target"] == "upload":
            ###import
            print("import")
            data = self.save_file("S3908-15.0.0")
            self.finish(data)
            return

        body = self.get_json_body()
        print(body)

        data = json.loads("{}")

        if params["target"] == 'log':
            print("GET LOG")
        elif params["target"] != 'unknown':
            partNumber = params["partnumber"]
            print(partNumber)

            if params["target"] == "lib":
                print("@@@LIB")

            elif params["target"] == "plan":
                if body["task"] == 'create':
                    print("create test")
                    ProductionTestsManager.createPlan(partNumber, params["plan"])
                elif body["task"] == 'run':
                    print("run test")
                    pid = self.run(partNumber, params["plan"])
                    self.finish({"id": pid})
                    return

                elif body["task"] == 'export':
                    print("export test")

                    tar_buffer = BytesIO()
                    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                        folder = ProductionTestsManager.getPlanFolder(partNumber, params["plan"])
                        tar.add(folder, arcname=os.path.basename(folder))

                    # Set the appropriate headers
                    self.set_header('Content-Type', 'application/x-tar')
                    self.set_header('Content-Disposition', 'attachment; filename="archive.tar"')

                    # Write the tar buffer contents as the response body
                    self.write(tar_buffer.getvalue())

                    return data

            elif params["target"] == "case":
                if body["name"] == params["case"]:
                    data = ProductionTestsManager.setCase(partNumber, params["plan"], body)
                else:
                    print("@@RENAME")
                    data = ProductionTestsManager.deleteCase(partNumber, params["plan"], params["case"])
                    data = ProductionTestsManager.setCase(partNumber, params["plan"], body)

        self.finish(data)

    @tornado.web.authenticated
    def delete(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        params = ProductionTestsV2Handler.get_params(subpath)

        data = json.loads("{}")

        if params["target"] == 'log':
            print("DELETE LOG")
        elif params["target"] != 'unknown':
            partNumber = params["partnumber"]
            print(partNumber)

            if params["target"] == "lib":
                print("@@@LIB")

            elif params["target"] == "plan":
                data = ProductionTestsManager.deletePlan(partNumber, params["plan"])

            elif params["target"] == "case":
                data = ProductionTestsManager.deleteCase(partNumber, params["plan"], params["case"])

        self.finish(data)
        

    def run(self, partNumber, plan):
        global g_production_test_log_id
        g_production_test_log_id = g_production_test_log_id + 1
        print("Test Log ID:", g_production_test_log_id)

        ProductionTestsManager.preRun(partNumber, plan)
        pt = ProductionTestsManager()
        global g_production_test_thread
        if g_production_test_thread is not None and g_production_test_thread.is_alive():
            pt.stopTests()
            g_production_test_thread.join()

        g_production_test_thread = threading.Thread(target=pt.run)
        g_production_test_thread.start()

        print("production test thread start")
        return g_production_test_log_id

    def check_import_folder():
        data = {}
        temp_folder = os.path.join(webds.PRODUCTION_TEST_IMPORT_FOLDER, 'temp')
        print("CHECK FOLDER ", webds.PRODUCTION_TEST_IMPORT_FOLDER)
        for tar in listdir(webds.PRODUCTION_TEST_IMPORT_FOLDER):
            # un-tar
            tar_file = os.path.join(webds.PRODUCTION_TEST_IMPORT_FOLDER, tar)
            print("TAR FILE:", tar_file)
            SystemHandler.CallSysCommand(['mkdir', temp_folder])
            SystemHandler.CallSysCommand(['tar','-xf', tar_file, '-C', temp_folder])

            try:
                for f in listdir(temp_folder):
                    print("TAR UNTAR plan name:", f)
                    path = os.path.join(temp_folder, f)
                    data = ProductionTestsManager.importTestPlan(path)
            except Exception as e:
                print("exception!!!", e)
                #### raise HttpServerError(str(e))
                #### error handling fixme
            finally:
                SystemHandler.CallSysCommand(['rm', '-rf', tar_file])
                SystemHandler.CallSysCommand(['rm', '-rf', temp_folder])
            return data

    def save_file(self, partnumber):
        data = json.loads("{}")

        if len(self.request.files.items()) is 0:
            message = "request.files.items len=0"
            raise HttpServerError(message)

        for field_name, files in self.request.files.items():
            for f in files:
                filename, content_type = f["filename"], f["content_type"]
                body = f["body"]

                fname =  os.path.join(webds.PRODUCTION_TEST_IMPORT_FOLDER, filename)
                # save temp hex file in worksapce
                with open(fname, 'wb') as f:
                    f.write(body)

        return ProductionTestsV2Handler.check_import_folder()