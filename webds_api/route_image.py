import tornado
from jupyter_server.base.handlers import APIHandler

import os
import json
import binascii
from . import webds
from .touchcomm_manager import TouchcommManager

config_label = [22, 229, 5, 124, 65, 80, 80, 95, 67, 79, 78, 70, 73, 71, 32, 32, 32, 32, 32, 32]


def le2int(foo):
    return int.from_bytes(foo, byteorder="little")


def int2le(foo, num_bytes):
    return list(foo.to_bytes(num_bytes, "little"))


class ImageHandler(APIHandler):
    def _update_config(self, body):
        tc = TouchcommManager().getInstance()
        num_areas = le2int(body[4:8])
        config_offset = 0
        for i in range(num_areas):
            entry = 8 + i * 4
            offset = le2int(body[entry:entry+4])
            if body[offset:offset+20] == config_label:
                config_offset = offset
                break

        if config_offset == 0:
            raise RuntimeError("Configuration area not found.")

        config_size = le2int(body[config_offset+28:config_offset+32])

        identify = tc.identify()
        if le2int(body[config_offset+36+14:config_offset+36+18]) != identify["buildID"]:
            raise RuntimeError("Mismatching build IDs.")

        app_info = tc.getAppInfo()
        tc.enterBootloaderMode()
        boot_info = tc.getBootInfo()

        first_word = app_info["appConfigBlock"] * boot_info["writeBlockWords"]
        num_words = config_size / 2

        config_words = tc.readFlash(first_word, num_words)
        config_bytes = []
        for x in config_words:
            config_bytes += int2le(x, 2)
        tc.runApplicationFirmware()

        body[config_offset+36:config_offset+36+config_size] = config_bytes

        config_bytearray = bytes(config_bytes)
        crc = binascii.crc32(config_bytearray)
        body[config_offset+32:config_offset+36] = int2le(crc, 4)

    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    async def post(self):
        input_data = self.get_json_body()
        packrat_id = input_data["packrat_id"]

        try:
            body = []
            file_names = [os.path.join(webds.PACKRAT_CACHE, packrat_id, "PR" + packrat_id + ".img")]
            file_names.append(os.path.join(webds.WORKSPACE_PACKRAT_DIR, packrat_id, "PR" + packrat_id + ".img"))
            for file_name in file_names:
                try:
                    with open(file_name, "rb") as f:
                        body = list(f.read())
                        break
                except IOError:
                    pass
            if body == []:
                raise RuntimeError("Base image file not found.")
            self._update_config(body)
        except Exception as e:
            print(e)
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))

        try:
            data = {"data": body}
            self.set_header("content-type", "application/json")
            self.finish(json.dumps(data))
        except tornado.iostream.StreamClosedError:
            print("iostream.StreamClosedError")
        except Exception as e:
            print(e)
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))
