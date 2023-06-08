import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpBrokenPipe, HttpServerError, HttpBadRequest, HttpNotFound
import threading
from multiprocessing import Queue, Lock
import sys
import time
import re


def read_symbol(file_path):
    try:
        result_dict = {}
        is_symbol_table = False  # Flag to indicate if we are in the symbol table section

        with open(file_path, 'r') as file:
            for line in file:
                if is_symbol_table:
                    pattern = r'(\w+)=(REG)\s+\$([\dA-F]+)'
                    matches = re.findall(pattern, line)
                    if matches:
                        result_dict[matches[0][0]] = matches[0][2]

                if "Symbol table:" in line:
                    is_symbol_table = True

        return result_dict

    except FileNotFoundError:
        raise Exception(f"File '{file_path}' not found.")
    except IOError:
        raise Exception(f"Error reading file '{file_path}'.")
    except Exception as e:
        print(str(e))

class RamBackdoorHandler(APIHandler):

    _thread = None
    _queue = None
    _terminate = False
    _sse_lock = Lock()
    _app_mode = None

    def resetQueue():
        if RamBackdoorHandler._queue is None:
            RamBackdoorHandler._queue = Queue()
        else:
            while not RamBackdoorHandler._queue.empty():
                RamBackdoorHandler._queue.get()
        print("RESET QUEUE DONE")

    def read_ram(tc, address):
        start_time = time.time()

        values = []

        if len(address) == 0:
            raise HttpServerError("empty array")

        for r in address:
            try:
                v = tc.function("readRam", args = [r["address"], r["length"]])
                values.append(v)
            except Exception as e:
                print(e, hex(r))
                values.append(None)
                pass

        print("--- %s seconds ---" % (time.time() - start_time))
        return values

    def check_sse_terminated():
        print("CHECK SSE THREAD TERMINATE...")
        for i in range(200):
            if RamBackdoorHandler._sse_lock.acquire(False):
                return
            time.sleep(0.01)
        print("SSE THREAD TEMINATED PROPERLY!!!")

    def terminate_sse():
        print("SEND SIGNAL TO TERMINATE QUEUE")
        if RamBackdoorHandler._queue:
            RamBackdoorHandler._queue.put({"status": "terminate"})

    @tornado.web.authenticated
    def get(self):
        try:
            query = self.get_query_argument("query")
            packrat = self.get_query_argument("packrat")
        except:
            query = None

        if query == 'table':
            try:
                folders = [webds.WORKSPACE_PACKRAT_DIR, webds.WORKSPACE_PACKRAT_CACHE_DIR]
                for root in folders:
                    file_path = os.path.join(root, str(packrat), "PR" + str(packrat) + ".hex")
                    if not os.path.exists(file_path):
                        print("file_path", file_path)
                        continue
                    symbol_table = read_symbol(file_path)
                    self.finish(symbol_table)
                    return
                raise HttpServerError("Hex File not found.")
            except Exception as e:
                raise HttpServerError("Parsing failed")
        elif query is None:
            return self.getSSE()
        else:
            raise HttpNotFound()

    def sse_command(self, data):
        try:
            tc = TouchcommManager()
        except Exception as e:
            RamBackdoorHandler._terminate = True
            print(str(e))
            print("THREAD EXCEPTION TERMINATED")
            RamBackdoorHandler.terminate_sse()
            return

        ###data = {
        ###          interval: 500,
        ###          data: [
        ###              {"address": xxxx, length: xxxx},
        ###              {"address": xxxx, length: xxxx},
        ###          ]
        ###}

        while True:
            start_time = time.time()
            message = {"status": "run", "data": []}
            for idx, ram in enumerate(data["data"]):
                if RamBackdoorHandler._terminate:
                    break

                try:
                    v = tc.function("readRam", args = [ram["address"], ram["length"]])
                    message["data"].append({"address": ram["address"], "data": v})
                    ##print("[MESSAGE] ", message)
                except Exception as e:
                    ### user directly close jupyterlab or queue has been terminated
                    print(e, r)
                    print("THREAD EXCEPTION TERMINATED")
                    RamBackdoorHandler.terminate_sse()
                    return

            if RamBackdoorHandler._terminate:
                break

            elapsed_time = time.time() - start_time
            interval_seconds = data["interval"] / 1000  # Convert interval to seconds

            if elapsed_time < interval_seconds:
                time.sleep(interval_seconds - elapsed_time)

            RamBackdoorHandler._queue.put(message)

        if RamBackdoorHandler._terminate:
            RamBackdoorHandler._queue.put({"status": "terminate"})
            RamBackdoorHandler.terminate_sse()
        else:
            RamBackdoorHandler._queue.put({"status": "done"})
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
        name="RamBackdoor"
        RamBackdoorHandler._sse_lock.acquire()
        print("SSE LOOP START")
        try:
            while True:
                if RamBackdoorHandler._queue is not None:
                    token = RamBackdoorHandler._queue.get()
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
            print("Broken Pipe Error", e)

        finally:
            RamBackdoorHandler._terminate = True
            while not RamBackdoorHandler._queue.empty():
                RamBackdoorHandler._queue.get()

            RamBackdoorHandler._sse_lock.release()
            print("SSE TERMINATED")


    def check_thread_status():
        if RamBackdoorHandler._thread is not None and RamBackdoorHandler._thread.is_alive():
            RamBackdoorHandler._terminate = True
            RamBackdoorHandler._thread.join()
        print("THREAD IS INACTIVE")

        RamBackdoorHandler._terminate = False
        print("THREAD STATUS CHECK PASS")

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        response = {}

        if "command" in data:
            command = data["command"]

            print(command)
            if command == "terminate":
                print("terminate request")
                if RamBackdoorHandler._thread is not None:
                    RamBackdoorHandler._terminate = True
                    RamBackdoorHandler._thread.join()
                self.finish(json.dumps({"status": "terminate"}))
                return

            if "sse" in data:
                sse = data["sse"]
            else:
                sse = False

            tc = TouchcommManager()
            tc.function("unlockPrivate")

            if sse:
                RamBackdoorHandler.check_thread_status()
                RamBackdoorHandler.resetQueue()
                print("QUEUE RESET")
                RamBackdoorHandler._thread = threading.Thread(target=self.sse_command, args=(data["data"],))
                RamBackdoorHandler._thread.start()

                self.finish(json.dumps({
                  "status": "start",
                }))
                return

            elif command == "read":
                alist = data["data"]
                tc = TouchcommManager()
                value = RamBackdoorHandler.read_ram(tc, alist)

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
                        v = tc.function("writeRegister", [r["address"], r["value"]])
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