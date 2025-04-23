import pyads
import datetime
import time
import threading
import json
import os
import control
from pk import PK

actual_value_name = 'PRG_HE.FB_Haus_28_42_12_17_15_VL_Temp.fOut'
control_bwk_name = 'PRG_WV.FB_Brenner.BWS.iStellung'

# Lock for parameters
parameter_lock = threading.Lock()
threshold = 60 # degrees
auto_duration_minutes = 10

plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
plc.open()

class EMA:
  def __init__(self, decay_factor):
    self.decay_factor = decay_factor
    self.last = None

  def update(self, value, dt):
    if self.last is None:
      self.last = value
      return self.last
    with parameter_lock:
      last_weight = self.decay_factor ** dt
    self.last = last_weight * self.last + (1 - last_weight) * value
    return self.last

last_update_dt = None
value_ema = EMA(0.5 ** (1/60)) # 50% per minute
auto_off_dt = None

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'bwk_onoff_params.json')

def load_parameters():
  try:
    with open(PARAMS_FILE, 'r') as f:
      params = json.load(f)
      set_parameters(params)
  except FileNotFoundError:
    pass

def save_parameters():
  params = get_parameters()
  with open(PARAMS_FILE, 'w') as f:
    json.dump(params, f)

def set_parameters(params):
  global value_ema, threshold, auto_duration_minutes
  with parameter_lock:
    value_ema.decay_factor = params.get('decay_factor', value_ema.decay_factor)
    threshold = params.get('threshold', threshold)
    auto_duration_minutes = params.get('auto_duration_minutes', auto_duration_minutes)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {'decay_factor': value_ema.decay_factor, 'threshold': threshold, 'auto_duration_minutes': auto_duration_minutes}

def control_loop():
  global last_update_dt, value_ema, auto_off_dt
  diagnostics = {}
  now = datetime.datetime.now()
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()
  try:
    actual_value = plc.read_by_name(actual_value_name)
    current_control_bwk = plc.read_by_name(control_bwk_name)
    pk = PK(plc)
    pk.read()

    now = datetime.datetime.now()
    diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

    dt = (now - last_update_dt).total_seconds() if last_update_dt else None
    last_update_dt = now
    value_ema.update(actual_value, dt)
    diagnostics['value'] = round(actual_value, 2)
    diagnostics['value_ema'] = round(value_ema.last, 2)
    diagnostics['bwk'] = control.control_str(current_control_bwk)
    if auto_off_dt:
      diagnostics['auto_off'] = auto_off_dt.replace(microsecond=0).isoformat()

    if current_control_bwk != control.ON:
      if value_ema.last < threshold:
        plc.write_by_name(control_bwk_name, control.AUTO)
        diagnostics['control_bwk'] = 'auto'
        auto_off_dt = now + datetime.timedelta(minutes=auto_duration_minutes)
        diagnostics['auto_off'] = auto_off_dt.replace(microsecond=0).isoformat()
        return diagnostics

    if current_control_bwk == control.OFF:
      if auto_off_dt is not None:
        auto_off_dt = None
        diagnostics['auto_off'] = 'superceded'
        return diagnostics

    if current_control_bwk == control.AUTO:
      if auto_off_dt is None:
        auto_off_dt = now + datetime.timedelta(minutes=auto_duration_minutes)
        diagnostics['auto_off'] = auto_off_dt.replace(microsecond=0).isoformat()
        return diagnostics
      if now >= auto_off_dt:
        auto_off_dt = None
        diagnostics['auto_off'] = 'expired'
        diagnostics['pk'] = pk.diagnostics()
        if not pk.is_available():
          diagnostics['control_bwk'] = 'ignored (PK not available)'
          return diagnostics
        plc.write_by_name(control_bwk_name, control.OFF)
        diagnostics['control_bwk'] = 'off'
        return diagnostics

  except Exception as e:
    diagnostics['exception'] = repr(e)
    print(e)

  diagnostics['idle'] = True
  return diagnostics

def main(stop_requested):
  while not stop_requested():
    diagnostics = control_loop()
    print(diagnostics.pop('timestamp'), end=' ')
    print(diagnostics, flush=True)

    try:
      time.sleep(5)
    except:
      break
  return 0

load_parameters()

if __name__ == '__main__':
  exit(main(lambda: False))


