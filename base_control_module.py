import pyads
import threading
import json
import os
import datetime
from abc import ABC, abstractmethod

class BaseControlModule(ABC):
  def __init__(self, plc_ams_net_id, plc_ams_port, param_filename, param_dir=None):
    self.plc_ams_net_id = plc_ams_net_id
    self.plc_ams_port = plc_ams_port
    self.plc = None
    self.parameter_lock = threading.Lock()
    self.param_filename = param_filename
    self.param_dir = param_dir or os.path.dirname(__file__)
    self.PARAMS_FILE = os.path.join(self.param_dir, self.param_filename)
    self.enabled = True
    self.plc = pyads.Connection(self.plc_ams_net_id, self.plc_ams_port)
    self.plc.open()

  def reopen_plc(self):
    try:
      self.plc.close()
    except Exception:
      pass
    self.plc.open()

  def load_parameters(self):
    try:
      with open(self.PARAMS_FILE, 'r') as f:
        params = json.load(f)
        self.set_parameters(params)
    except FileNotFoundError:
      self.save_parameters()

  def save_parameters(self):
    params = self.get_parameters()
    with open(self.PARAMS_FILE, 'w') as f:
      json.dump(params, f)

  def set_parameters(self, params):
    with self.parameter_lock:
      self.enabled = params.get('enabled', self.enabled)
      self._set_module_parameters(params)
    self.save_parameters()

  def get_parameters(self):
    with self.parameter_lock:
      params = {'enabled': self.enabled}
      params.update(self._get_module_parameters())
      return params

  @abstractmethod
  def _set_module_parameters(self, params):
    pass

  @abstractmethod
  def _get_module_parameters(self):
    pass

  def control_loop(self):
    with self.parameter_lock:
      if not self.plc.is_open:
        self.plc.open()
      diagnostics = {}
      now = datetime.datetime.now()
      diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()
      if not self.enabled:
        diagnostics['disabled'] = True
        return diagnostics
      try:
        diagnostics |= self._control_action(now)
      except pyads.ADSError as e:
        diagnostics['exception'] = repr(e)
        self.plc.close()
        self.reopen_plc()
      except Exception as e:
        diagnostics['exception'] = repr(e)
        print(e)
      return diagnostics

  @abstractmethod
  def _control_action(self, now):
    pass
