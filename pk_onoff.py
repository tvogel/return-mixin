import pyads
import datetime
import time
import threading
import json
import os

on1_value_name = 'PRG_HE.FB_Speicher_1_Temp_oben.fOut'
on2_value_name = 'PRG_HE.FB_Speicher_2_Temp_oben.fOut'
off1_value_name = 'PRG_HE.FB_Speicher_1_Temp_unten.fOut'
off2_value_name = 'PRG_WV.FB_BHKW_RL_Temp.fOut'
control_pk_name = 'PRG_WV.FB_Pelletkessel.BWS.iStellung'
pk_available_name = 'PRG_WV.FB_Pelletkessel_AT_Gw.bQ'
CONTROL_AUTO = 1
CONTROL_OFF = 2
CONTROL_ON = 3

def control_str(control):
  return {CONTROL_AUTO: 'auto', CONTROL_OFF: 'off', CONTROL_ON: 'on'}.get(control, control)

# Lock for parameters
parameter_lock = threading.Lock()
on_threshold = 64 # degrees
off_threshold = 58 # degrees

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
on_value_ema = EMA(0.5 ** (1/60)) # 50% per minute
off_value_ema = EMA(0.5 ** (1/60)) # 50% per minute

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'pk_onoff_params.json')

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
  global on_value_ema, off_value_ema, on_threshold, off_threshold
  with parameter_lock:
    on_value_ema.decay_factor = params.get('decay_factor', on_value_ema.decay_factor)
    off_value_ema.decay_factor = params.get('decay_factor', off_value_ema.decay_factor)
    on_threshold = params.get('on_threshold', on_threshold)
    off_threshold = params.get('off_threshold', off_threshold)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {
        'decay_factor': on_value_ema.decay_factor,
        'on_threshold': on_threshold,
        'off_threshold': off_threshold
    }

def control_loop():
  global last_update_dt, on_value_ema, off_value_ema
  diagnostics = {}
  now = datetime.datetime.now()
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()
  try:
    on1_value = plc.read_by_name(on1_value_name)
    on2_value = plc.read_by_name(on2_value_name)
    off1_value = plc.read_by_name(off1_value_name)
    off2_value = plc.read_by_name(off2_value_name)
    current_control_pk = plc.read_by_name(control_pk_name)
    current_pk_available = plc.read_by_name(pk_available_name)
    now = datetime.datetime.now()
    diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

    dt = (now - last_update_dt).total_seconds() if last_update_dt else None
    last_update_dt = now
    on_value_ema.update(min(on1_value, on2_value), dt)
    off_value_ema.update(max(off1_value, off2_value), dt)
    diagnostics['on_value_ema'] = round(on_value_ema.last, 2)
    diagnostics['off_value_ema'] = round(off_value_ema.last, 2)
    diagnostics['pk'] = control_str(current_control_pk)
    diagnostics['pk_available'] = current_pk_available

    if not current_pk_available and current_control_pk == CONTROL_ON:
        plc.write_by_name(control_pk_name, CONTROL_OFF)
        diagnostics['control'] = 'off'
        return diagnostics

    if current_control_pk == CONTROL_ON and off_value_ema.last >= off_threshold:
        plc.write_by_name(control_pk_name, CONTROL_OFF)
        diagnostics['control'] = 'off'
        return diagnostics

    if current_control_pk == CONTROL_OFF and on_value_ema.last <= on_threshold:
        plc.write_by_name(control_pk_name, CONTROL_ON)
        diagnostics['control'] = 'on'
        return diagnostics

    diagnostics['idle'] = True
    return diagnostics

  except Exception as e:
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


