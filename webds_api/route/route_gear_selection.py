import json

import tornado
from jupyter_server.base.handlers import APIHandler

from ..tuning.gear_selection_manager import GearSelectionManager
from ..errors import HttpServerError

class GearSelectionHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        print("GearSelectionHandler POST")

        input_data = self.get_json_body()
        print(input_data)

        gsm = GearSelectionManager()

        try:
            fn = input_data["function"]
            args = None
            if "arguments" in input_data:
                args = input_data["arguments"]
            retval = gsm.function(fn, args)
            self.finish(json.dumps(retval))
            return
        except Exception as e:
            print("GearSelectionHandler POST Exception")
            raise HttpServerError(str(e))

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, data):
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: gear-selection\n')
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()
        except tornado.iostream.StreamClosedError:
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self):
        print("GearSelectionHandler GET")

        cur_progress = 0

        gsm = GearSelectionManager()

        try:
            while True:
                total, progress, sweep = gsm.get_progress()
                if sweep == "completed" or sweep == "stopped":
                    gsm.join()
                    self.set_header("content-type", "text/event-stream")
                    self.write("id: {}\n".format(sweep))
                    self.write("data: {}\n".format(gsm.get_noise_output()))
                    self.write('\n')
                    yield self.flush()
                    break
                elif cur_progress != progress:
                        send = {
                            "total" : total,
                            "progress" : progress,
                        }
                        yield self.publish(json.dumps(send))
                        cur_progress = progress
                yield tornado.gen.sleep(0.0005)
        except tornado.iostream.StreamClosedError:
            print("GearSelectionHandler SSE Stream Closed")
            gsm.stop(True)
            pass
        except Exception as e:
            print("GearSelectionHandler GET Exception")
            raise HttpServerError(str(e))
        finally:
            gsm.reset_progress()
