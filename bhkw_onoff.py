#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import datetime
import time
import threading
import json
import os
from suntimes import SunTimes
from ema import EMA
import control
from pk import PK
from buffer_tank import BufferTank

latitude = 52.371582
longitude = 12.932913
altitude = 31

control_bhkw_name = 'PRG_WV.FB_BHKW.BWS.iStellung'

last_update = None

enabled = True

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

buffer_tank = BufferTank(plc, 64, 58)

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
  global enabled
  with parameter_lock:
    enabled = params.get('enabled', enabled)
    buffer_tank.set_parameters(params)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return { 'enabled': enabled } | buffer_tank.parameters()

def determine_control_value(current, solar_available, pk_available):
  if not solar_available:
    return control.ON
  if pk_available:
    return control.OFF
  if (buffer_tank_control := buffer_tank.get_control()) != None:
    return buffer_tank_control
  return current

def control_loop():
  global last_update
  diagnostics = {}
  now = datetime.datetime.now()
  dt = (now - last_update).total_seconds() if last_update else None
  last_update = now
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

  if not enabled:
    diagnostics['disabled'] = True
    return diagnostics

  try:
    with parameter_lock:
      buffer_tank.update(dt)
      diagnostics |= buffer_tank.diagnostics()

      solar_available = solar_is_available(now)
      diagnostics['solar_available'] = solar_available

      pk = PK(plc)
      pk.read()
      diagnostics['pk'] = pk.diagnostics()

      current_bhkw = control.invert(plc.read_by_name(control_bhkw_name))
      diagnostics['bhkw'] = control.control_str(current_bhkw)
      new_bhkw = determine_control_value(current_bhkw, solar_available, pk.is_available())

    if current_bhkw != new_bhkw:
      plc.write_by_name(control_bhkw_name, control.invert(new_bhkw))
      diagnostics['control_bhkw'] = control.control_str(new_bhkw)
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


