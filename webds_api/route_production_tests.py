import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json

import time
from .production_test_manager import ProductionTestsManager
import threading

g_production_test_thread = None

class ProductionTestsHandler(APIHandler):
    def sse(self):
        try:
            while True:
                if self is not None:
                    send = {
                        "progress": "111",
                    }
                    yield self.publish(json.dumps(send))
                    yield gen.sleep(0.0001)
                else:
                    yield gen.sleep(1)

        except StreamClosedError:
            message="stream closed"
            print(message)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        print("sse finished")

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
    def get(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)
        print(subpath)
        print(cluster_id)
        print(self.request.arguments)

        data = json.loads("{}")
        if subpath is "":
            ### GET/SSE
            sse()
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
        global g_production_test_thread
        if g_production_test_thread is not None and g_production_test_thread.is_alive():
            g_program_thread.join()

        pt = ProductionTestsManager()
        g_production_test_thread = threading.Thread(target=pt.run)
        g_production_test_thread.start()
        print("production test thread start")