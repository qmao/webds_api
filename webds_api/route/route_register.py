import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpBrokenPipe, HttpServerError, HttpBadRequest, HttpNotFound
import threading
from multiprocessing import Queue, Lock
import sys
import time


REGISTER_FOLDER = '/var/cache/syna/register_map/sb7900'
REGISTER_FILE = 'regs_sb7900_riscv.json'

class RegisterHandler(APIHandler):

    _thread = None
    _queue = None
    _terminate = False
    _sse_lock = Lock()
    _app_mode = None

    def resetQueue():
        if RegisterHandler._sse_lock.acquire(False):
            RegisterHandler._sse_lock.release()
        else:
            RegisterHandler._sse_lock.release()

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
            raise HttpServerError(str(e))

    def read_registers(tc, address):
        start_time = time.time()

        values = []

        if len(address) == 0:
            raise HttpServerError("empty array")

        for r in address:
            try:
                v = tc.function("readRegister", args = [r, RegisterHandler._app_mode])
                values.append(v)
            except Exception as e:
                print(e, hex(r))
                values.append(None)
                pass

        print("--- %s seconds ---" % (time.time() - start_time))
        return values

    def check_mode():
        try:
            tc = TouchcommManager()
            id = tc.function("identify")

            if id['mode'] == 'rombootloader':
                print("In RomBoot Mode")
                RegisterHandler._app_mode = False
            elif id['mode'] == 'application':
                print("In Application Mode")
                tc.function("unlockPrivate")
                RegisterHandler._app_mode = True

                ###print("Force jump to RomBoot Mode")
                ###tc.enterRomBootloaderMode()
                ###id = tc.identify()
                ###print(id['mode'])
                ###print("Jump to RomBoot Mode done")
            else:
                print(id['mode'])

            return id['mode']

        except Exception as e:
            print("CHECK FW MODE EXCEPTION", str(e))
            raise e

    def check_sse_terminated():
        print("CHECK SSE THREAD TERMINATE...")
        for i in range(200):
            if RegisterHandler._sse_lock.acquire(False):
                return
            time.sleep(0.01)
        print("[ERROR] SSE THREAD TEMINATED PROPERLY!!!")

    def terminate_sse():
        print("SEND SIGNAL TO TERMINATE QUEUE")
        if RegisterHandler._queue:
            RegisterHandler._queue.put({"status": "terminate"})

    @tornado.web.authenticated
    def get(self):
        return self.getSSE()

    def sse_command(self, command, data):
        print("sse command", command)

        try:
            tc = TouchcommManager()
        except Exception as e:
            RegisterHandler._terminate = True
            print(str(e))
            print("THREAD EXCEPTION TERMINATED")
            RegisterHandler.terminate_sse()
            return

        for idx, r in enumerate(data):
            ##start_time = time.time()
            if RegisterHandler._terminate:
                print("detect terminate flag")
                break
            try:
                if command == "read":
                    v = tc.function("readRegister", args = [r, RegisterHandler._app_mode])
                    message = {"status": "run", "address": r, "value": v, "index": idx, "total": len(data)}
                elif command == "write":
                    v = tc.function("writeRegister", args = [r["address"], r["value"], RegisterHandler._app_mode])
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
                ###print("DEBUG:", {"status": "run", "address": r, "value": None, "index": idx, "total": len(data)})
            except Exception as e:
                ### user directly close jupyterlab
                ### queue has been terminated
                print(e, r)
                print("THREAD EXCEPTION TERMINATED")
                RegisterHandler.terminate_sse()
                return
            ##print("--- %s seconds ---" % (time.time() - start_time))

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

        RegisterHandler._sse_lock.acquire()
        try:
            while True:
                if RegisterHandler._queue is None:
                    continue

                token = RegisterHandler._queue.get()
                if token is not None:
                    yield self.publish(name, json.dumps(token))

                if token['status'] == 'done' or token['status'] == 'terminate':
                    print("sse terminate token", token)
                    break

                yield tornado.gen.sleep(0.001)

        except StreamClosedError:
            print("Stream Closed!")

        except Exception as e:
            ### BrokenPipeError
            print("Broken Pipe Error")

        finally:
            RegisterHandler._terminate = True
            while not RegisterHandler._queue.empty():
                RegisterHandler._queue.get()

            RegisterHandler._sse_lock.release()
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
                    raise HttpServerError(str(e))

                self.finish(json.dumps(content))
                return

            elif command == "terminate":
                print("terminate request")
                RegisterHandler._terminate = True
                RegisterHandler._thread.join()
                self.finish(json.dumps({"status": "terminate"}))
                return

            elif command == "check_mode":
                RegisterHandler.check_thread_status()
                try:
                    mode = RegisterHandler.check_mode()
                    self.finish(json.dumps({"status": "done", "mode": mode}))
                except Exception as e:
                    raise HttpServerError(str(e))
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
                tc = TouchcommManager()
                value = RegisterHandler.read_registers(tc, alist)

                self.finish(json.dumps({
                  "data": value
                }))
                return

            elif command == "write":
                status = []
                tc = TouchcommManager()
                address = data["data"]
                value = []
                alist = []

                if len(address) == 0:
                    raise HttpServerError("empty array")

                for r in address:
                    try:
                        ###print("write", hex(r["address"]),  r["value"])
                        v = tc.function("writeRegister", [r["address"], r["value"], RegisterHandler._app_mode])
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
            raise HttpBadRequest("command not set")

        raise HttpNotFound()