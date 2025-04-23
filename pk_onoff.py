import pyads
import datetime
import time
import threading
import json
import os
import control
from pk import PK
from buffer_tank import BufferTank

# Lock for parameters
parameter_lock = threading.Lock()

plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
plc.open()

buffer_tank = BufferTank(plc, 64, 58)

last_update_dt = None

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
  with parameter_lock:
    buffer_tank.set_parameters(params)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return buffer_tank.parameters()

def control_loop():
  global last_update_dt
  diagnostics = {}
  now = datetime.datetime.now()
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()
  dt = (now - last_update_dt).total_seconds() if last_update_dt else None

  try:
    pk = PK(plc)
    pk.read()

    now = datetime.datetime.now()
    diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

    buffer_tank.update(dt)

    last_update_dt = now

    diagnostics |= buffer_tank.diagnostics()
    diagnostics['pk'] = pk.diagnostics()

    new_control_pk = pk.control

    if not pk.is_available():
        new_control_pk = control.OFF
    elif (buffer_tank_control := buffer_tank.get_control()) != None:
        new_control_pk = buffer_tank_control

    if pk.set_control(new_control_pk):
        diagnostics['control'] = control.control_str(new_control_pk)
        return diagnostics

    diagnostics['idle'] = True
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


