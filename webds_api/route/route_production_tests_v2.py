import tornado
from tornado.iostream import StreamClosedError
from tornado import gen
from jupyter_server.base.handlers import APIHandler
import os
import json
import threading
import time
from ..production_test_v2.production_test_manager import ProductionTestsManager
from ..errors import HttpStreamClosed, HttpServerError
import os

g_production_test_thread = None

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
                            yield self.publish(json.dumps(send))
                        elif status == 'done':
                            send = {
                                "index" : index,
                                "name"  :  name,
                                "status" : status,
                                "result" : outcome
                            }
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
            
        elif params["target"] == 'log':
            print("GET LOG")
        else:
            partNumber = params["partnumber"]
            print(partNumber)

            if params["target"] == "lib":
                if query == 'lib':
                    data = ProductionTestsManager.getLib(partNumber)
                elif query == 'plans':
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
    def post(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        params = ProductionTestsV2Handler.get_params(subpath)
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
                if body["task"] == 'run':
                    print("run test")
                    self.run(partNumber, params["plan"])
                print("@@@PLAN")

            elif params["target"] == "case":
                print("@@@CASE", params["plan"], body)
                data = ProductionTestsManager.setCase(partNumber, params["plan"], body)
                print("QQQQQQQQQQQQQQQ", data)

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
                print("@@@PLAN")

            elif params["target"] == "case":
                data = ProductionTestsManager.deleteCase(partNumber, params["plan"], params["case"])
                print("QQQQQQQQQQQQQQQ", data)

        self.finish(data)
        
        
        
    def run(self, partNumber, plan):
        ProductionTestsManager.preRun(partNumber, plan)
        pt = ProductionTestsManager()
        global g_production_test_thread
        if g_production_test_thread is not None and g_production_test_thread.is_alive():
            pt.stopTests()
            g_production_test_thread.join()

        g_production_test_thread = threading.Thread(target=pt.run)
        g_production_test_thread.start()
        print("production test thread start")