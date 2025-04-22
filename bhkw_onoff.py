import pyads
import datetime
import time
import threading
import json
import os
from suntimes import SunTimes
from ema import EMA

CONTROL_AUTO = 1
CONTROL_OFF = 2
CONTROL_ON = 3

latitude = 52.371582
longitude = 12.932913
altitude = 31

control_bhkw_name = 'PRG_WV.FB_BHKW.BWS.iStellung'
pk_available_name = 'PRG_WV.FB_Pelletkessel_AT_Gw.bQ'
pk_stoerung_name = 'PRG_WV.FB_Pelletkessel.bStoerung'

on1_value_name = 'PRG_HE.FB_Speicher_1_Temp_oben.fOut'
on2_value_name = 'PRG_HE.FB_Speicher_2_Temp_oben.fOut'
off1_value_name = 'PRG_HE.FB_Speicher_1_Temp_unten.fOut'
off2_value_name = 'PRG_WV.FB_BHKW_RL_Temp.fOut'

on_threshold = 64 # degrees
off_threshold = 58 # degrees

on_value_ema = EMA(0.5 ** (1/60)) # 50% per minute
off_value_ema = EMA(0.5 ** (1/60)) # 50% per minute

last_update = None

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
  global on_threshold, off_threshold
  with parameter_lock:
    on_threshold = params.get('on_threshold', on_threshold)
    off_threshold = params.get('off_threshold', off_threshold)
    on_value_ema.decay_factor = params.get('decay_factor', on_value_ema.decay_factor)
    off_value_ema.decay_factor = params.get('decay_factor', off_value_ema.decay_factor)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {
      'on_threshold': on_threshold,
      'off_threshold': off_threshold,
      'decay_factor': on_value_ema.decay_factor
    }


def determine_control_value(current, solar_available, pk_available, on_value, off_value):
  if not solar_available:
    return CONTROL_ON
  if pk_available:
    return CONTROL_OFF
  if off_value > off_threshold:
    return CONTROL_OFF
  if on_value < on_threshold:
    return CONTROL_ON
  return current

def control_loop():
  global last_update, on_value_ema, off_value_ema

  diagnostics = {}
  now = datetime.datetime.now()
  dt = (now - last_update).total_seconds() if last_update else None
  last_update = now
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

  try:
    with parameter_lock:
      on1_value = plc.read_by_name(on1_value_name)
      on2_value = plc.read_by_name(on2_value_name)
      off1_value = plc.read_by_name(off1_value_name)
      off2_value = plc.read_by_name(off2_value_name)

      on_value = on_value_ema.update(min(on1_value, on2_value), dt)
      off_value = off_value_ema.update(max(off1_value, off2_value), dt)
      diagnostics['on_value_ema'] = round(on_value, 2)
      diagnostics['off_value_ema'] = round(off_value, 2)

      solar_available = solar_is_available(now)
      diagnostics['solar_available'] = solar_available
      pk_available = plc.read_by_name(pk_available_name)
      diagnostics['pk_available'] = pk_available
      pk_stoerung = plc.read_by_name(pk_stoerung_name)
      diagnostics['pk_stoerung'] = pk_stoerung
      current_bhkw = swap_control(plc.read_by_name(control_bhkw_name))
      diagnostics['bhkw'] = control_str(current_bhkw)
      new_bhkw = determine_control_value(current_bhkw, solar_available, pk_available and not pk_stoerung, on_value, off_value)

    if current_bhkw != new_bhkw:
      plc.write_by_name(control_bhkw_name, swap_control(new_bhkw))
      diagnostics['control_bhkw'] = control_str(new_bhkw)
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


