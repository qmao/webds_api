import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
import sys
import time


REGISTER_FOLDER = '/home/dsdkuser/jupyter/workspace/'


class RegisterHandler(APIHandler):

    def read_register_file(src):
        try:
            with open (src, 'r' ) as f:
                content = f.read()
                return content
        except:
            print('[ERROR ] ', dst, " not created!!!!!")
            return None

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
        tc = TouchcommManager().getInstance()
        id = tc.identify()

        if id['mode'] == 'rombootloader':
            print("In RomBoot Mode")
        elif id['mode'] == 'application':
            print("In Application Mode")
            ###tc.unlockPrivate()

            try:
                print("Force jump to RomBoot Mode")
                tc.enterRomBootloaderMode()

                id = tc.identify()
                print(id['mode'])
            except Exception as e:
                print(e)
        else:
            print(id['mode'])

    @tornado.web.authenticated
    def get(self):
        print(self.request)

        self.finish(json.dumps({
            "data": "register get is running"
        }))

    @tornado.web.authenticated
    def post(self):
        data = self.get_json_body()
        print(data)
        response = {}

        if "command" in data:
            command = data["command"]
            print(command)
            if command == "init":
                ### mode check
                RegisterHandler.check_mode()

                ### read register file
                fname = os.path.join(REGISTER_FOLDER, 'regs_sb7900_riscv.json')
                content = RegisterHandler.read_register_file(fname)
                self.finish(json.dumps(content))
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
                    alist.append(r["address"])

                print("STATUS:", status)
                value = RegisterHandler.read_registers(tc, alist)

                self.finish(json.dumps({
                  "data": value,
                  "status": status
                }))
                return
        else:
            print("command not set")

        raise tornado.web.HTTPError(status_code=400, log_message="unsupported action")