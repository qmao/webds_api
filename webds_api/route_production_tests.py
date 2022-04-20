import tornado
from tornado.iostream import StreamClosedError
from tornado import gen
from jupyter_server.base.handlers import APIHandler
import os
import json

import time
from .production_test_manager import ProductionTestsManager
import threading

g_production_test_thread = None

class ProductionTestsHandler(APIHandler):
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
        ###print(self.request.arguments)

        data = json.loads("{}")
        if subpath is "":
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
                    message="stream closed"
                    print(message)
                    pt.stopTests()
                    raise tornado.web.HTTPError(status_code=400, log_message=message)
        else:
            partNumber = subpath[1:]
            print(partNumber)

            data = ProductionTestsManager.getTests(partNumber)

            self.finish(data)

    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        data = json.loads("{}")

        if subpath is not "":
            partNumber = subpath[1:]
            print(partNumber)

            input_data = self.get_json_body()
            print(input_data)

            test = input_data["test"]
            print(test)

            if test == "all":
                print("run all tests")
                self.run(partNumber)
            else:
                print("run test: ", test)
                self.run(partNumber, test)
        else:
            raise tornado.web.HTTPError(status_code=400, log_message=str('partnumber not found'))

        self.finish(data)

    @tornado.web.authenticated
    def put(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)

        data = json.loads("{}")

        if subpath is not "":
            partNumber = subpath[1:]
            print(partNumber)

            input_data = self.get_json_body()
            print(input_data)

            sets_file = ProductionTestsManager.setTests(partNumber, input_data)

            data = { "message": str(sets_file) }
        else:
            raise tornado.web.HTTPError(status_code=400, log_message=str('partnumber not found'))

        self.finish(data)


    def run(self, partNumber, id = None):
        ProductionTestsManager.preRun(partNumber, id)
        pt = ProductionTestsManager()
        global g_production_test_thread
        if g_production_test_thread is not None and g_production_test_thread.is_alive():
            pt.stopTests()
            g_production_test_thread.join()

        g_production_test_thread = threading.Thread(target=pt.run)
        g_production_test_thread.start()
        print("production test thread start")