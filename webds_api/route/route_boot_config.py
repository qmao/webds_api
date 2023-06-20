import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
import time
import struct
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError, HttpNotFound
from ..boot_config.lockdown import LockdownStructure


def split_path(path):
    paths = []
    if path == '':
        return paths
    while path != '/':
        path, part = os.path.split(path)
        paths.append(part)

    paths.append(path)
    paths.reverse()
    return paths

def little_endian_to_byte_array(values):
    byte_array = bytearray()
    for value in values:
        # Convert each value to a little-endian byte array using struct.pack
        bytes_value = struct.pack('<H', value)
        # Extend the byte array with the bytes from the little-endian value
        byte_array.extend(bytes_value)

    # Convert the bytearray to a list of integers
    int_list = list(byte_array)
    return int_list

class BootConfigHandler(APIHandler):

    def get_boot_info(self, tc):
        id = tc.function("identify")
        if id["mode"] == "application":
            tc.function("enterBootloaderMode")
        return tc.function("getBootInfo")

    def get_boot_config(self, tc):
        boot = self.get_boot_info(tc)
        boot_config_start = boot["bootConfigStartBlock"] * boot["writeBlockWords"]
        boot_config_len = boot["bootConfigBlocks"]* boot["writeBlockWords"]
        config = tc.function("readFlash", args=[boot_config_start, boot_config_len])
        return little_endian_to_byte_array(config)

    def get_lockdown(self, tc):
        boot = self.get_boot_info(tc)
        boot_config_start = boot["bootConfigStartBlock"] * boot["writeBlockWords"]
        boot_config_len = boot["bootConfigBlocks"]* boot["writeBlockWords"]
        lockdown_start = boot_config_start + boot_config_len - 8
        config = tc.function("readFlash", args=[lockdown_start, 8])
        return little_endian_to_byte_array(config)

    def get_custom_serialization(self, tc):
        boot = self.get_boot_info(tc)
        cs_start = boot["bootConfigStartBlock"] * boot["writeBlockWords"]
        cs_len = boot["bootConfigBlocks"]* boot["writeBlockWords"] - 8
        config = tc.function("readFlash", args=[cs_start, cs_len])
        return little_endian_to_byte_array(config)

    def write_to_cs(self, tc, data):
        boot = self.get_boot_info(tc)
        boot_config_start = boot["bootConfigStartBlock"] * boot["writeBlockWords"]

        cs_start = boot_config_start
        cs_len = boot["bootConfigBlocks"]* boot["writeBlockWords"] - 8
        config = tc.function("readFlash", args=[cs_start, cs_len])

        word_array = []
        for i in range(0, len(data), 2):
            two_bytes = data[i+1] << 8 | data[i]
            word_array.append(two_bytes)

        for i in range(0, len(word_array), 4):
            default = config[i:i+4]
            group = word_array[i:i+4]

            if any(group) and not any(default):
                print("WRITE", i, group)
                ret = tc.function("writeFlash", args=[boot_config_start + i, group])
            else:
                print("Do nothing", i, group)

        return ""

    def write_to_lockdown(self, tc, data):
        boot = self.get_boot_info(tc)
        boot_config_start = boot["bootConfigStartBlock"] * boot["writeBlockWords"]
        boot_config_len = boot["bootConfigBlocks"]* boot["writeBlockWords"]

        word_array = []
        for i in range(0, len(data), 2):
            two_bytes = data[i+1] << 8 | data[i]
            word_array.append(two_bytes)

        ret = tc.function("writeFlash", args=[boot_config_start + boot_config_len - 4, word_array])
        return ""

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self, subpath: str = "", cluster_id: str = ""):
        print(self.request)
        print("subpath:", subpath)

        paths = split_path(subpath)
        print(paths)

        data = json.loads("{}")
        tc = TouchcommManager()
        if len(paths) is 0:
            print("GET BOOT CONFIG")
            config = self.get_boot_config(tc)
            data = {"data": config}

        elif len(paths) is 2:
            if paths[1] == "lockdown":
                print("GET lock down")
                config = self.get_lockdown(tc)

                isLocked = False
                user_config = config[8:16]
                for element in user_config:
                    if element != 0:
                        isLocked = True
                        break

                if isLocked:
                    lconfig = user_config
                else:
                    lconfig = config

                lockdown = LockdownStructure(lconfig)

                protocol = tc.getInstance().comm.get_interface()
                lockdown_data = lockdown.get_lockdown(protocol)

                lockdown_data["locked"] = isLocked
                data = {"data": lockdown_data}

            elif paths[1] == "custom-serialization":
                print("GET custom-serialization")
                config = self.get_custom_serialization(tc)
                data = {"data": config}
            else:
                raise HttpNotFound()
        else:
            raise HttpNotFound()

        self.finish(data)

    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        dataToSet = self.get_json_body()
        print(dataToSet)

        paths = split_path(subpath)
        print(paths)

        data = json.loads("{}")

        tc = TouchcommManager()

        if len(paths) is 0:
            print("Do NOT SUPPORT SET BOOT CONFIG")
            raise HttpNotFound()
        elif len(paths) is 2:
            try:
                if paths[1] == "lockdown":
                    print("SET lock down")
                    lockdown = LockdownStructure([0] * 4)
                    protocol = tc.getInstance().comm.get_interface()
                    lockdown.set_lockdown(dataToSet["data"], protocol)
                    lock_arr = lockdown.get_byte_array()

                    ret = self.write_to_lockdown(tc, lock_arr)

                    data["status"] = 1

                elif paths[1] == "custom-serialization":
                    print("SET custom-serialization")
                    ret = self.write_to_cs(tc, dataToSet["data"])
                    data["status"] = 1

                else:
                    raise HttpNotFound()
            except Exception as e:
                raise HttpServerError(str(e))
        else:
            raise HttpNotFound()

        self.finish(data)