import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from . import webds
from .utils import SystemHandler
from .file_manager import FileManager


def save(files, location):
    print(files)
    for f in files:
        filename, content_type = f["filename"], f["content_type"]
        body = f["body"]

        print(filename)

        data = json.loads("{}")
        data["filename"] = filename
        print(data)

        self.finish(json.dumps(data))
                
                
class FilesystemHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        print(self.request.arguments)

        location = self.request.arguments['location'][0].decode("utf-8")
        print(location)

        for label, files in self.request.files.items():
            print(label)
            for f in files:
                filename, content_type = f['filename'], f['content_type']
                print(filename, content_type)

                body = f["body"]
                
                # save temp hex file in worksapce
                with open(webds.WORKSPACE_TEMP_FILE, 'wb') as f:
                    f.write(body)
                    
                # move temp file to location
                file_path = os.path.join(location, filename)
                print(file_path)
                SystemHandler.CallSysCommand(['mv', webds.WORKSPACE_TEMP_FILE, file_path])

        data = {'data': 'done'}
        self.set_header('content-type', 'application/json')
        self.finish(json.dumps(data))

    @tornado.web.authenticated
    def get(self):
        print(self.request.arguments)
        folder = self.get_argument('dir', None)

        print(folder)
        if folder is not None:
            try:
                data = FileManager.GetTree(folder)
            except Exception as e:
                raise tornado.web.HTTPError(status_code=400, log_message=str(e))
        else:
            data = json.loads("{}")
        self.finish(data)