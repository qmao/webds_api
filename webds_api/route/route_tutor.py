import tornado
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
import sys
from ..tutor.tutor_initial_setup import InitialSetup

class TutorHandler(APIHandler):
    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self, subpath: str = "", cluster_id: str = ""):
        print("self.request:", self.request)
        print("subpath:",subpath)
        data = json.loads("{}")

        paths = subpath.split("/")

        if len(paths) == 1:
            tutor = paths[0]
            cls = globals()[tutor]
            function = getattr(cls, 'get')
            data = function()

        self.finish(data)

    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        input_data = self.get_json_body()
        print(input_data)

        paths = subpath.split("/")

        if len(paths) == 1:
            tutor = paths[0]
            cls = globals()[tutor]
            function = getattr(cls, 'post')
            data = function(input_data)

        self.finish(data)