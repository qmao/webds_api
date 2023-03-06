import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
import threading
from multiprocessing import Queue, Value
import queue
import sys
import time


REGISTER_FOLDER = '/var/cache/syna/register_map/sb7900'
REGISTER_FILE = 'regs_sb7900_riscv.json'

class RegisterHandler(APIHandler):

    _thread = None
    _queue = None
    _terminate = False
    _sse_terminate = Value('i', 0)

    def resetQueue():
        RegisterHandler._sse_terminate.value = 0
        if RegisterHandler._queue is None:
            RegisterHandler._queue = Queue()
        else:
            while not RegisterHandler._queue.empty():
                RegisterHandler._queue.get()

        print("RESET QUEUE DONE")

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

        if len(address) == 0:
            raise tornado.web.HTTPError(status_code=400, log_message="empty array")

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
            print("CHECK FW MODE EXCEPTION", str(e))
            raise e

    def terminate_sse():
        print("SEND SIGNAL TO TERMINATE QUEUE")
        RegisterHandler._queue.put({"status": "terminate"})
        RegisterHandler._sse_terminate.value = 1
        print("WAIT QUEUE TO STOP")
        for i in range(200):
            if RegisterHandler._queue.empty():
                break
            time.sleep(0.01)

        if RegisterHandler._queue.empty() == False:
            print("[ERROR] SSE NOT CLOSE PROPERLY!!!")

    @tornado.web.authenticated
    def get(self):
        return self.getSSE()

    def sse_command(self, command, data):
        print("sse command", command)

        try:
            tc = TouchcommManager().getInstance()
        except Exception as e:
            RegisterHandler._terminate = True
            print(str(e))
            print("THREAD EXCEPTION TERMINATED")
            return

        for idx, r in enumerate(data):
            if RegisterHandler._terminate:
                print("detect terminate flag")
                break
            try:
                if command == "read":
                    v = tc.readRegister(r)
                    message = {"status": "run", "address": r, "value": v, "index": idx, "total": len(data)}
                elif command == "write":
                    v = tc.writeRegister(r["address"], r["value"])
                    if r["value"] == None:
                        raise "value is None"
                    message = {"status": "run", "address": r["address"], "value": r["value"], "index": idx, "total": len(data)}
            except Exception as e:
                ### rw failed
                print(e, r)
                if command == "read":
                    RegisterHandler._queue.put({"status": "run", "address": r, "value": None, "index": idx, "total": len(data)})
                elif command == "write":
                    message = {"status": "run", "address": r["address"], "value": None, "index": idx, "total": len(data)}
                pass

            try:
                RegisterHandler._queue.put(message)
            except Exception as e:
                ### user directly close jupyterlab
                ### queue has been terminated
                print(e, r)
                print("THREAD EXCEPTION TERMINATED")
                return

        if RegisterHandler._terminate:
            RegisterHandler.terminate_sse()
        else:
            RegisterHandler._queue.put({"status": "done"})
        print("THREAD NORMAL TERMINATED")

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

        while True:
            try:
                if RegisterHandler._queue is None:
                    yield tornado.gen.sleep(0.1)
                    continue

                token = RegisterHandler._queue.get()
                if token is not None:
                    ### print("----**** SSE", token)
                    yield self.publish(name, json.dumps(token))

                if token['status'] == 'done' or token['status'] == 'terminate':
                    print("sse terminate token", token)
                    break

                if RegisterHandler._sse_terminate.value == 1:
                    print("sse terminate value detect")
                    break

                yield tornado.gen.sleep(0.1)

            except StreamClosedError:
                print("Stream Closed!")
                break

            except Exception as e:
                ### TypeError
                ### BrokenPipeError
                print("Oops! get report", e.__class__, "occurred.")
                print(e)

        RegisterHandler._terminate = True
        while not RegisterHandler._queue.empty():
            RegisterHandler._queue.get()

        print("SSE TERMINATED")


    def check_thread_status():
        if RegisterHandler._thread is not None and RegisterHandler._thread.is_alive():
            RegisterHandler._terminate = True
            RegisterHandler._thread.join()
        print("THREAD IS INACTIVE")

        RegisterHandler._terminate = False
        print("THREAD STATUS CHECK PASS")

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        response = {}

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
                RegisterHandler._terminate = True
                RegisterHandler._thread.join()
                RegisterHandler.terminate_sse()
                self.finish(json.dumps({"status": "terminate"}))
                return

            elif command == "check_mode":
                RegisterHandler.check_thread_status()
                try:
                    RegisterHandler.check_mode()
                    self.finish(json.dumps({"status": "done"}))
                except Exception as e:
                    print(str(e))
                    raise tornado.web.HTTPError(status_code=400, log_message=str(e))
                return

            if "sse" in data:
                sse = data["sse"]
            else:
                sse = False

            if sse:
                RegisterHandler.check_thread_status()
                RegisterHandler.resetQueue()
                print("QUEUE RESET")
                RegisterHandler._thread = threading.Thread(target=self.sse_command, args=(command, data["data"]))
                RegisterHandler._thread.start()

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

                if len(address) == 0:
                    raise tornado.web.HTTPError(status_code=400, log_message="empty array")

                for r in address:
                    try:
                        ###print("write", hex(r["address"]),  r["value"])
                        v = tc.writeRegister(r["address"], r["value"])
                        alist.append(r["value"])
                    except Exception as e:
                        status.append({"address": hex(r["address"]), "error": str(e) })
                        alist.append(None)
                        pass

                self.finish(json.dumps({
                  "data": alist,
                  "status": status
                }))
                return
        else:
            print("command not set")

        raise tornado.web.HTTPError(status_code=400, log_message="unsupported action")