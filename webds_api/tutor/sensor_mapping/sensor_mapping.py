import sys
import re
import time
import json


class SensorMapping():
    _handle = None
    _start = None
    _debug = False
    _terminate = False
    _terminated = False
    _static_config = {}
    _dynamic_config = {}

    def __init__(self, handle):
        self._handle = handle
        self._static_config = self._handle.getStaticConfig()
        self._dynamic_config = self._handle.getDynamicConfig()
        self._touch_info = self._handle.getTouchInfo()
        self._app_info = self._handle.getAppInfo()

        self._terminate = False
        self._terminated = False

           