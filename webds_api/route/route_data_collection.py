import tornado
from jupyter_server.base.handlers import APIHandler

import json
import gzip
from os.path import exists
from ..utils import SystemHandler

DATA_COLLECTION_STASH = "/var/spool/syna/data_collection/testrail/stash"
DATA_COLLECTION_TEMP = "/home/dsdkuser/jupyter/workspace/.cache/stash.cache"

class DataCollectionHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        stash = {"stash": []}
        stash_file = DATA_COLLECTION_STASH

        try:
            if exists(stash_file):
                with gzip.open(stash_file, "r") as f:
                    stash = json.load(f)
        except json.decoder.JSONDecodeError:
            pass
        except Exception as e:
            print("DataCollectionHandler GET Exception\n{}".format(str(e)))
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))

        self.finish(json.dumps(stash))

    @tornado.web.authenticated
    def post(self):
        stash = {"stash": []}
        stash_file = DATA_COLLECTION_STASH
        temp_file = DATA_COLLECTION_TEMP

        input_data = self.get_json_body()
        request = input_data["request"]

        if request == "append":
            try:
                data = input_data["data"]
                if exists(stash_file):
                    with gzip.open(stash_file, "r") as f:
                        stash = json.load(f)
            except json.decoder.JSONDecodeError:
                pass
            except Exception as e:
                print("DataCollectionHandler POST Exception\n{}".format(str(e)))
                raise tornado.web.HTTPError(status_code=400, log_message=str(e))
            stash["stash"].append(data)
        elif request == "overwrite":
            try:
                data = input_data["data"]
            except Exception as e:
                print("DataCollectionHandler POST Exception\n{}".format(str(e)))
                raise tornado.web.HTTPError(status_code=400, log_message=str(e))
            stash = data
        elif request == "flush":
            pass
        else:
            e = "invalid request: {}".format(request)
            print("DataCollectionHandler POST Exception\n{}".format(e))
            raise tornado.web.HTTPError(status_code=400, log_message=e)

        try:
            with gzip.open(temp_file, "wt", encoding="utf-8") as zip_file:
                json.dump(stash, zip_file, ensure_ascii=False, indent=2)
            SystemHandler.CallSysCommand(["mv", temp_file, stash_file])
            SystemHandler.CallSysCommandFulfil("chown root:root " + stash_file)
        except Exception as e:
            print("DataCollectionHandler POST Exception\n{}".format(str(e)))
            raise tornado.web.HTTPError(status_code=400, log_message=str(e))

        self.finish()
