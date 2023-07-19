import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError


from pathlib import Path
import zlib


class ImageParser:
    def __init__(self, fileName):
        self._fileName = fileName
        with open(fileName, mode='rb') as file: # b is important -> binary
            self._fileContent = file.read()

    def le2int(data):
        return int.from_bytes(data, byteorder="little")


    def int2le(data, num_bytes):
        return list(data.to_bytes(num_bytes, "little"))

    def calculate_crc32(data):
        crc32 = zlib.crc32(data)
        return crc32

    def checkHeader(self):
        ##hexFormat = ' '.join(hex(byte) for byte in fileContentRange)
        identifier = ImageParser.le2int(self._fileContent[0: 4])
        if identifier != 0x4818472B:
            print("INVALID IMAGE FILE. identifier:", identifier)
            return False
        else:
            print(hex(identifier))
            return True

    def getNumberOfMemoryAreas(self):
        count = ImageParser.le2int(self._fileContent[4: 8])
        return count

    def getMemoryAreaList(self):
        count = self.getNumberOfMemoryAreas()
        alist = []
        for number in range(count):
            start = 8 + 4*number
            offset = ImageParser.le2int(self._fileContent[start : start + 4])
            area = {}
            area["id"] = bytes(self._fileContent[offset + 4 : offset + 20]).decode('utf-8', errors='ignore').strip()
            area["identifier"] = hex(ImageParser.le2int(self._fileContent[offset : offset + 4]))
            area["flag"] = ImageParser.le2int(self._fileContent[offset + 20 : offset + 24])
            area["address"] = hex(ImageParser.le2int(self._fileContent[offset + 24 : offset + 28]))
            area["length"] = ImageParser.le2int(self._fileContent[offset + 28 : offset + 32])
            area["offset"] = offset
            area["crc"] = hex(ImageParser.le2int(self._fileContent[offset + 32 : offset + 36]))

            ##data = self._fileContent[offset + 36 : offset + 36 + area["length"]]
            ##crc = ImageParser.calculate_crc32(data)
            ##print("CRC:", hex(crc))

            alist.append(area)
        return alist


class ImageHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        input_data = self.get_json_body()
        print(input_data)

        try:
            command = input_data["command"]
            if "payload" in input_data:
                payload = input_data["payload"]
            else:
                payload = None

            print(command)
            print(payload)

            tc = TouchcommManager()
            response = tc.function(command, payload)
        except Exception as e:
            raise HttpServerError(str(e))

        self.finish(json.dumps(response))

    @tornado.web.authenticated
    def get(self, cluster_id: str = ""):
        print(self.request)

        param = cluster_id.split("/")
        print(param)

        data = json.loads("{}")
        filename = ""
        if len(param) == 3:
            packrat = param[1]
            filename = param[2]
        else:
            raise HttpNotFound()

        try:
            if packrat is not None and filename is not None:
                filename = os.path.join(webds.PACKRAT_CACHE, packrat, filename)
                print("FILE NAME:", filename)
                f = ImageParser(filename)
                if f.checkHeader() is False:
                    raise HttpServerError("Unsupported image file format")
                data["data"] = f.getMemoryAreaList()
                print(data)


        except Exception as e:
            raise HttpServerError(str(e))

        self.finish(data)