import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import time
import os
import threading

from web_api import start_control_loops, app

print("Starting service\n")
print("Working directory: %s\n" % os.getcwd())

class PyADSService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PyADSService"
    _svc_display_name_ = "PyADS Control Loop Service"
    _svc_description_ = "Runs the PyADS control loop as a Windows service."

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

    def main(self):
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
