import os
import glob
import json
from tornado import iostream, gen
from .. import webds
from ..utils import SystemHandler

class FileManager():
    def GetFileList(extension):
        filelist = []
        os.chdir(webds.PACKRAT_CACHE)
        for file in glob.glob("**/*." + extension):
            print(file)
            filelist += [str(file)]

        data = json.loads("{}")
        data["filelist"] = filelist

        jsonString = json.dumps(data)
        return jsonString

    async def downloadBlob(Handler, content):
        try:
            Handler.write(content)
            await Handler.flush()
            print("write flush")
        except iostream.StreamClosedError:
            print("iostream error")
        finally:
            print("iostream finally")
            # pause the coroutine so other handlers can run
            await gen.sleep(0.000000001) # 1 nanosecond

    async def download(Handler, filename):
        # chunk size to read
        chunk_size = 1024 * 1024 * 1 # 1 MiB

        if not os.path.exists(filename):
            raise Exception(filename + " not exist")
        with open(filename, 'rb') as f:
            while True:
                print("ready to read file")
                chunk = f.read(chunk_size)
                if not chunk:
                    print("not chunk")
                    break
                try:
                    Handler.write(chunk)
                    await Handler.flush()
                    print("write flush")
                except iostream.StreamClosedError:
                    print("iostream error")
                    break
                finally:
                    print("iostream finally")
                    del chunk
                    # pause the coroutine so other handlers can run
                    await gen.sleep(0.000000001) # 1 nanosecond

    def GetTree(path):
        try:
            if not os.path.exists(path):
                raise Exception(path + " not exist")
            d = {'name': os.path.basename(path)}
            if os.path.isdir(path):
                d['type'] = "directory"
                d['children'] = [FileManager.GetTree(os.path.join(path,x)) for x in os.listdir (path)]
            else:
                d['type'] = "file"
            return d
        except Exception as e:
            print(e)
            raise e