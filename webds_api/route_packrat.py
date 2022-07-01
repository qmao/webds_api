import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json

from . import webds
from .utils import HexFile, SystemHandler
from .file_manager import FileManager

class PackratHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    async def get(self, cluster_id: str = ""):
        print(self.request)

        param = cluster_id.split("/")
        packrat_id = None
        filename = None
        data = {}

        if len(param) > 3:
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        if len(param) > 1:
            packrat_id = param[1]
        if len(param) > 2:
            filename = param[2]

        if packrat_id and filename:
            ###/packrat/{packrat_id}/{filename}
            try:
                file_type = self.get_argument('type', None)
                if file_type and file_type != 'base':
                    print("implement image function here", filename)
                else:
                    filename = os.path.join(webds.PACKRAT_CACHE, packrat_id, filename)
                    print(filename)
                    await FileManager.download(self, filename)
                    data = None
            except Exception as e:
                print(e)
                raise tornado.web.HTTPError(status_code=400, log_message=str(e))
        elif packrat_id is not None:
            ###/packrat/{packrat_id}
            raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        else:
            ###/packrat?extension=json
            extension = self.get_argument('extension', None)
            data = json.loads("{}")

            if extension:
                filelist = FileManager.GetFileList(extension)
                data = filelist
            else:
                raise tornado.web.HTTPError(status_code=405, log_message="Not implement")
        self.finish(data)

    @tornado.web.authenticated
    def post(self, packrat_id: str = ""):
        print(self.request)

        if packrat_id:
            packrat = packrat_id[1:]
            print(packrat)
            self.save_file(packrat)
        else:
            return self.save_file()

    @tornado.web.authenticated
    def delete(self, packrat_id: str = ""):
        print(self.request)
        input_data = self.get_json_body()

        filename = os.path.join(webds.PACKRAT_CACHE, packrat_id[1:], input_data["file"])
        print("delete file: ", filename)
        SystemHandler.CallSysCommand(['rm', filename])
        SystemHandler.UpdateWorkspace()

        self.finish(json.dumps("{delete: yes}"))

    def save_file(self, packrat_id=None):
        for field_name, files in self.request.files.items():
            print(field_name)
            for f in files:
                filename, content_type = f["filename"], f["content_type"]
                body = f["body"]
                #logging.info(
                #    'POST "%s" "%s" %d bytes', filename, content_type, len(body)
                #)
                print(filename)

                if packrat_id is None:
                # user upload a hex file from local drive
                    try:
                        packrat_id = HexFile.GetSymbolValue("PACKRAT_ID", body.decode('utf-8'))
                        print(packrat_id)
                        filename = "PR" + packrat_id + ".hex"
                        print("new file name:" + filename)
                    except:
                        message = filename + " PACKRAT_ID parse failed"
                        raise tornado.web.HTTPError(status_code=400, log_message=message)
                        return
                    if packrat_id is None:
                        message = filename + " PACKRAT_ID not found"
                        raise tornado.web.HTTPError(status_code=400, log_message=message)
                        return

                # save temp hex file in worksapce
                with open(webds.WORKSPACE_TEMP_FILE, 'wb') as f:
                    f.write(body)

                # move temp hex to packrat cache
                path = os.path.join(webds.PACKRAT_CACHE, packrat_id)
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