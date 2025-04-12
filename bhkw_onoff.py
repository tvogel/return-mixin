import pyads
import datetime
import time
import threading
import json
import os
from suntimes import SunTimes

latitude = 52.371582
longitude = 12.932913
altitude = 31

control_bhkw_name = 'PRG_WV.FB_BHKW.BWS.iStellung'
pk_available_name = 'PRG_WV.FB_Pelletkessel_AT_Gw.bQ'
CONTROL_AUTO = 1
CONTROL_OFF = 2
CONTROL_ON = 3

def swap_control(control):
  if control == CONTROL_ON:
    return CONTROL_OFF
  if control == CONTROL_OFF:
    return CONTROL_ON
  return control

def control_str(control):
  return {CONTROL_AUTO: 'auto', CONTROL_OFF: 'off', CONTROL_ON: 'on'}.get(control, control)

def solar_is_available(now = datetime.datetime.now(), offset = datetime.timedelta(hours=2)):
  sun = SunTimes(longitude, latitude, altitude)
  now = now.astimezone()
  sunrise = sun.riselocal(now)
  sunset = sun.setlocal(now)
  return now - sunrise > offset and sunset - now > offset

# Lock for parameters
parameter_lock = threading.Lock()

plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
plc.open()

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'bhkw_onoff_params.json')

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
  return
  global value_ema, threshold, auto_duration_minutes
  with parameter_lock:
    value_ema.decay_factor = params.get('decay_factor', value_ema.decay_factor)
    threshold = params.get('threshold', threshold)
    auto_duration_minutes = params.get('auto_duration_minutes', auto_duration_minutes)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {}
    return {'decay_factor': value_ema.decay_factor, 'threshold': threshold, 'auto_duration_minutes': auto_duration_minutes}

def control_loop():
  diagnostics = {}
  now = datetime.datetime.now()
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()
  try:
    solar_available = solar_is_available(now)
    diagnostics['solar_available'] = solar_available
    pk_available = plc.read_by_name(pk_available_name)
    diagnostics['pk_available'] = pk_available
    current_bhkw = swap_control(plc.read_by_name(control_bhkw_name))
    diagnostics['bhkw'] = control_str(current_bhkw)
    new_bhkw = CONTROL_OFF if solar_available and pk_available else CONTROL_ON

    if current_bhkw != new_bhkw:
      plc.write_by_name(control_bhkw_name, swap_control(new_bhkw))
      diagnostics['control_bhkw'] = control_str(new_bhkw)
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


