import tornado
from tornado.iostream import StreamClosedError
from jupyter_server.base.handlers import APIHandler
import os
import json
from .. import webds
from ..utils import SystemHandler
from ..touchcomm.touchcomm_manager import TouchcommManager
from ..report.report_manager import ReportManager
import time
from copy import deepcopy


fps = 300
debug = True


class ReportHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self, subpath: str = "", cluster_id: str = ""):
        input_data = self.get_json_body()
        print(input_data)
        frameRate = None
        debugLog = None

        try:
            enable = input_data["enable"]
        except:
            pass
        try:
            disable = input_data["disable"]
        except:
            pass
        try:
            frameRate = input_data["fps"]
        except:
            pass
        try:
            debugLog = input_data["debug"]
        except:
            pass

        try:
            manager = ReportManager()
            manager.setState('pause')

            tc = TouchcommManager()

            for x in disable:
                print('disable:{}'.format(x))
                ret = tc.disableReport(x)

            for x in enable:
                print('enable:{}'.format(x))
                ret = tc.enableReport(x)

            manager.setState('resume')

            if frameRate is not None:
                global fps
                fps = frameRate
                print('fps:{}'.format(fps))

            if debugLog is not None:
                global debug
                debug = debugLog
                print('debug:{}'.format(debug))

            data = {'data': 'done'}

        except Exception as e:
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        self.set_header('content-type', 'application/json')
        self.finish(json.dumps(data))

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def publish(self, data):
        """Pushes data to a listener."""
        try:
            self.set_header('content-type', 'text/event-stream')
            self.write('event: report\n')
            self.write('data: {}\n'.format(data))
            self.write('\n')
            yield self.flush()
        except StreamClosedError:
            raise

    def getSSE(self):
        print("get report")

        manager = None
        frame_count = 0
        try:
            manager = ReportManager()
            manager.setState('start')
            global fps
            step = 1 / fps
            report_count = 0
            t0 = time.time()
            t00 = t0
            while True:
                t1 = time.time()
                if (t1 - t00 >= step):
                    t00 = t1
                    data = manager.getReport()
                    if frame_count != data[1]:
                        report = deepcopy(data[0])
                        if report[0] == 'delta' or report[0] == 'raw':
                            report[1]['image'] = report[1]['image']
                        report_count += 1
                        send = {"report": report, "frame": report_count}
                        yield self.publish(json.dumps(send))
                        frame_count = data[1]
                    else:
                        yield self.publish(json.dumps({}))
                if (t1 - t0 >= 1):
                    t0 = t1
                    print(str(report_count) + ' fps', flush = True)
                    report_count = 0
                yield tornado.gen.sleep(0.0001)

        except StreamClosedError:
            print("Stream Closed!")
            pass

        except Exception as e:
            ### TypeError
            ### BrokenPipeError
            print("Oops! get report", e.__class__, "occurred.")
            print(e)
            message=str(e)
            raise tornado.web.HTTPError(status_code=400, log_message=message)

        finally:
            if manager:
                print("Finally stop report manager")
                manager.setState('stop')

    def getReportOneShot(self, rtype):
        reportType = {
          "touch": 17,
          "delta": 18,
          "raw" : 19,
          "baseline": 20
        }

        disable=[]
        enable=[]
        for k, v in reportType.items():
            print(k, v)
            if k == rtype:
                enable.append(v)
            else:
                disable.append(v)
        tc = TouchcommManager()

        for x in disable:
            print('disable:{}'.format(x))
            ret = tc.disableReport(x)

        for x in enable:
            print('enable:{}'.format(x))
            ret = tc.enableReport(x)


        data = tc.getReport()
        if data[0] == rtype:
            send = {"report": data[1]['image']}
        else:
            message=str("report not found" + data)
            raise tornado.web.HTTPError(status_code=400, log_message=message)
        return send

    @tornado.web.authenticated
    @tornado.gen.coroutine
    def get(self, subpath: str = "", cluster_id: str = ""):
        print("self.request:", self.request)
        print("subpath:",subpath)

        data = json.loads("{}")

        paths = subpath.split("/")

        if len(paths) == 1:
            return self.getSSE()
        elif len(paths) > 1:
            tc = TouchcommManager()
            disable=[17,18,19]
            enable=[20]
            for x in disable:
                print('disable:{}'.format(x))
                ret = tc.disableReport(x)
            for x in enable:
                print('enable:{}'.format(x))
                ret = tc.enableReport(x)

            report = self.getReportOneShot(paths[1])
            self.finish(json.dumps(report))