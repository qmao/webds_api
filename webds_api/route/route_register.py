import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
import threading
from multiprocessing import Queue
import sys
import time


REGISTER_FOLDER = '/var/cache/syna/register/sb7900'
REGISTER_FILE = 'regs_sb7900_riscv.json'
g_thread = None
g_queue = None
g_terminate = False

class RegisterHandler(APIHandler):

    def resetQueue():
        global g_queue
        if g_queue is None:
            g_queue = Queue()
        else:
            while not g_queue.empty():
                g_queue.get()

    def read_register_file(src):
        try:
            with open (src, 'r' ) as f:
                content = f.read()
                return content
        except Exception as e:
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))

    def read_registers(tc, address):
        start_time = time.time()

        values = []

        for r in address:
            try:
                v = tc.readRegister(r)
                values.append(v)
            except Exception as e:
                print(e, hex(r))
                values.append(None)
                pass

        print("--- %s seconds ---" % (time.time() - start_time))
        return values

    def check_mode():
        try:
            tc = TouchcommManager().getInstance()
            id = tc.identify()

            if id['mode'] == 'rombootloader':
                print("In RomBoot Mode")
            elif id['mode'] == 'application':
                print("In Application Mode")
                ###tc.unlockPrivate()

                print("Force jump to RomBoot Mode")
                tc.enterRomBootloaderMode()
                id = tc.identify()
                print(id['mode'])
                print("Jump to RomBoot Mode done")
            else:
                print(id['mode'])

        except Exception as e:
            raise e

    @tornado.web.authenticated
    def get(self):
        return self.getSSE()

    def sse_command(self, command, data):
        print("sse command", command, data)
        global g_queue
        global g_terminate
        tc = TouchcommManager().getInstance()
        for idx, r in enumerate(data):
            if g_terminate:
                print("detect terminate flag")
                break
            try:
                if command == "read":
                    v = tc.readRegister(r)
                    g_queue.put({"status": "run", "address": r, "value": v, "index": idx, "total": len(data)})
                elif command == "write":
                    v = tc.writeRegister(r["address"], r["value"])
                    g_queue.put({"status": "run", "address": r["address"], "value": r["value"], "index": idx, "total": len(data)})
            except Exception as e:
                print(e, r)
                if command == "read":
                    g_queue.put({"status": "run", "address": r, "value": None, "index": idx, "total": len(data)})
                else:
                    g_queue.put({"status": "run", "address": r["address"], "value": None, "index": idx, "total": len(data)})
                pass

        if g_terminate:
            g_queue.put({"status": "terminate"})
        else:
            g_queue.put({"status": "done"})
        print("thread will be terminated")

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, name, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: {}\n'.format(name))
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()

        except StreamClosedError:
            print("stream close error!!")
            raise

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def getSSE(self):
        print("SSE LOOP")
        name="Register"
        global g_queue
        try:
            while True:
                if g_queue is None:
                    yield tornado.gen.sleep(0.1)
                    continue

                token = g_queue.get()
                if token is not None:
                    yield self.publish(name, json.dumps(token))

                if token['status'] == 'done' or token['status'] == 'terminate':
                    print("terminate token", token)
                    break
                yield tornado.gen.sleep(0.1)

        except StreamClosedError:
            print("Stream Closed!")
            pass

        except Exception as e:
            ### TypeError
            ### BrokenPipeError
            print("Oops! get report", e.__class__, "occurred.")
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        finally:
            print("terminate")

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        print(data)
        response = {}
        global g_terminate
        global g_thread

        if "command" in data:
            command = data["command"]

            print(command)
            if command == "init":
                ### read register file
                try:
                    fname = os.path.join(REGISTER_FOLDER, REGISTER_FILE)
                    content = RegisterHandler.read_register_file(fname)
                except Exception as e:
                    print(str(e))
                    raise tornado.web.HTTPError(status_code=400, log_message=str(e))

                self.finish(json.dumps(content))
                return

            elif command == "terminate":
                print("terminate")
                g_terminate = True
                g_thread.join()
                self.finish(json.dumps({"status": "terminate"}))
                return

            elif command == "check_mode":
                try:
                    RegisterHandler.check_mode()
                    self.finish(json.dumps({"status": "done"}))
                except Exception as e:
                    print(str(e))
                    self.finish(json.dumps({"status": "failed", "error": str(e)}))
                return

            if "sse" in data:
                sse = data["sse"]
            else:
                sse = False

            if sse:
                RegisterHandler.resetQueue()
                g_terminate = False
                g_thread = threading.Thread(target=self.sse_command, args=(command, data["data"]))
                g_thread.start()

                self.finish(json.dumps({
                  "status": "start",
                }))
                return

            elif command == "read":
                alist = data["data"]
                tc = TouchcommManager().getInstance()
                value = RegisterHandler.read_registers(tc, alist)

                self.finish(json.dumps({
                  "data": value
                }))
                return

            elif command == "write":
                status = []
                tc = TouchcommManager().getInstance()
                address = data["data"]
                value = []
                alist = []

                for r in address:
                    try:
                        ###print("write", hex(r["address"]),  r["value"])
                        v = tc.writeRegister(r["address"], r["value"])
                    except Exception as e:
                        status.append({"address": hex(r["address"]), "error": str(e) })
                        pass
                    alist.append(r["value"])

                self.finish(json.dumps({
                  "data": alist,
                  "status": status
                }))
                return
        else:
            print("command not set")

        raise tornado.web.HTTPError(status_code=400, log_message="unsupported action")