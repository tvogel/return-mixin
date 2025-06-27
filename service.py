#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import time
import os
import threading
import pyads

from web_api import start_control_loops, app

print("Starting service\n")
print("Working directory: %s\n" % os.getcwd())

class PyADSService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PyADSService"
    _svc_display_name_ = "PyADS Control Loop Service"
    _svc_description_ = "Runs the PyADS control loop as a Windows service."
    _svc_deps_ = [ 'tcsyssrv' ]

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.stop_requested = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.stop_requested = True

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()

    def wait_for_twincat_route(self):
        plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
        plc.open()
        test_value_name = 'PRG_HE.FB_Haus_28_42_12_17_15_VL_Temp.fOut'

        while not self.stop_requested:
            try:
                plc.read_by_name(test_value_name)
                print('TwinCat route is up')
                break
            except pyads.ADSError:
                print('Waiting 5 seconds for TwinCat route')
                time.sleep(5)


    def main(self):
        self.wait_for_twincat_route()
        start_control_loops()
        api_thread = threading.Thread(target=app.run, kwargs={'host': 'localhost', 'port': 5000})
        api_thread.daemon = True
        api_thread.start()
        while not self.stop_requested:
            time.sleep(1)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PyADSService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PyADSService)
