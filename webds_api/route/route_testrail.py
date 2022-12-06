import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json

from .. import webds
from ..utils import SystemHandler
from ..file.file_manager import FileManager

class TestrailHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    async def get(self, cluster_id: str = ""):
        print(self.request)

        param = cluster_id.split("/")
        suite_id = None
        filename = None
        data = {}

        if len(param) > 3:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        if len(param) > 1:
            suite_id = param[1]
        if len(param) > 2:
            filename = param[2]

        if suite_id and filename:
            try:
                file_type = self.get_argument('type', None)
                filename = os.path.join(webds.TESTRAIL_CACHE, suite_id, filename)
                print(filename)
                await FileManager.download(self, filename)
                data = None
            except Exception as e:
                print(e)
                raise tornado.web.HTTPError(status_code=400, log_message=str(e))
        elif suite_id is not None:
            ###/testrail/suite/{suite_id}
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        else:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        self.finish(data)

    @tornado.web.authenticated
    def post(self, suite_id: str = ""):
        print(self.request)

        if suite_id:
            sid = suite_id[1:]
            print(sid)
            self.save_file(sid)
        else:
            raise tornado.web.HTTPError(status_code=405, log_message="unknown suite id")


    def save_file(self, suite_id):
        if len(self.request.files.items()) is 0:
            message = "request.files.items len=0"
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        for field_name, files in self.request.files.items():
            for f in files:
                filename, content_type = f["filename"], f["content_type"]
                body = f["body"]
                #logging.info(
                #    'POST "%s" "%s" %d bytes', filename, content_type, len(body)
                #)

                # save temp file in worksapce
                with open(webds.WORKSPACE_TEMP_FILE, 'wb') as f:
                    f.write(body)

                # move temp to suite cache
                path = os.path.join(webds.TESTRAIL_CACHE, suite_id)
                SystemHandler.CallSysCommand(['mkdir','-p', path])
                file_path = os.path.join(path, filename)
                print(file_path)

                SystemHandler.CallSysCommand(['mv', webds.WORKSPACE_TEMP_FILE, file_path])
                data = json.loads("{}")
                try:
                    SystemHandler.UpdateWorkspace()
                    data["filename"] = filename
                    print(data)
                    self.finish(json.dumps(data))
                except FileExistsError:
                    message = file_path + " exists."
                    print(message)
                    raise tornado.web.HTTPError(status_code=400, log_message=message)