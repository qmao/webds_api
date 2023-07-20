import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..errors import HttpServerError
from ..image.image_parser import ImageParser

from pathlib import Path


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