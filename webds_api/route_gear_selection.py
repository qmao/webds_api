import json

import tornado
from jupyter_server.base.handlers import APIHandler

from .gear_selection_manager import GearSelectionManager

class GearSelectionHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        print("GearSelectionHandler POST")

        input_data = self.get_json_body()
        print(input_data)

        try:
            gsm = GearSelectionManager()
            fn = input_data["function"]
            args = None
            if "arguments" in input_data:
                args = input_data["arguments"]
            retval = gsm.function(fn, args)
            self.finish(json.dumps(retval))
            return
        except Exception as e:
            print("GearSelectionHandler POST Exception")
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))

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

        try:
            gsm = GearSelectionManager()
            while True:
                total, progress, sweep = gsm.get_progress()
                if sweep == "completed":
                    gsm.join()
                    self.set_header("content-type", "text/event-stream")
                    self.write("id: completed\n")
                    self.write("data: {}\n".format(gsm.get_noise_output()))
                    self.write('\n')
                    yield self.flush()
                    gsm.reset_progress()
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
            pass
        except Exception as e:
            print("GearSelectionHandler GET Exception")
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))
