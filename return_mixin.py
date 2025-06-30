#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import datetime
import time
import threading
import json
import os

actual_value_name = 'PRG_HE.FB_Haus_28_42_12_17_15_VL_Temp.fOut'
control_value_name = 'PRG_HE.FB_Zusatzspeicher.FB_Speicherladeset_Pumpe.FB_BWS_Sollwert.FB_PmSw.fWert'
control_onoff_name = 'PRG_HE.FB_Zusatzspeicher.FB_Speicherladeset_Pumpe.BWS.iStellung'
consumer_names = [
  'PRG_HE.FB_Hk_Haus_7_8_11.FB_Pumpe.bBetrieb',
  'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.bBetrieb',
  'PRG_HE.FB_Hk_Haus_28_42.FB_Pumpe.bBetrieb',
  'PRG_HE.FB_TWW.FB_Ladepumpe.bBetrieb'
]

CONTROL_OFF = 2
CONTROL_ON = 3

set_point = 63.5

integration_decay_factor = 0.5 ** (1/300) # 50% per five minutes

Kp = 6 / 60 # percent per second per degree
Ki = 3 / 60 # percent per second per long-term degree
Kd = 900 / 60 # percent per second per degree change per second

control_range = (-30, 100)

# Lock for PID parameters
parameter_lock = threading.Lock()

plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
plc.open()

last_value = None
last_control = None
last_update = None
I_error = None
D_error = None

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'return_mixin_params.json')

enabled = True

def ema(last, value, dt, integration_decay_factor):
  if last is None:
    return value
  previous_weight = integration_decay_factor ** dt
  return previous_weight * last + (1 - previous_weight) * value

def fd1(last, value, dt):
  if last is None:
    return 0
  return (value - last) / dt

def load_parameters():
  try:
    with open(PARAMS_FILE, 'r') as f:
      params = json.load(f)
      set_parameters(params)
  except FileNotFoundError:
    save_parameters()

def save_parameters():
  params = get_parameters()
  with open(PARAMS_FILE, 'w') as f:
    json.dump(params, f)

def set_parameters(params):
  global Kp, Ki, Kd, set_point, control_range, integration_decay_factor, enabled
  with parameter_lock:
    enabled = params.get('enabled', enabled)
    Kp = params.get('Kp', Kp)
    Ki = params.get('Ki', Ki)
    Kd = params.get('Kd', Kd)
    set_point = params.get('set_point', set_point)
    control_range = (-params.get('off_range', -control_range[0]), control_range[1])
    integration_decay_factor = params.get('decay_factor', integration_decay_factor)
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {'enabled': enabled, 'Kp': Kp, 'Ki': Ki, 'Kd': Kd, 'set_point': set_point, 'off_range': -control_range[0], 'decay_factor': integration_decay_factor}

def any_consumer_on():
  for name in consumer_names:
    if plc.read_by_name(name):
      return True
  return False

def control_loop():
  global last_value, last_control, last_update, I_error, D_error, Kp, Ki, Kd

  diagnostics = {}

  if not enabled:
    diagnostics['disabled'] = True
    return diagnostics

  if last_control is None:
    last_control = plc.read_by_name(control_value_name) \
      if plc.read_by_name(control_onoff_name) == CONTROL_ON \
      else control_range[0]

  try:
    now = datetime.datetime.now()
    dt = (now - last_update).total_seconds() if last_update else None
    last_update = now
    diagnostics['dt'] = dt

    if not any_consumer_on():
      plc.write_by_name(control_onoff_name, CONTROL_OFF)
      plc.write_by_name(control_value_name, 0)
      diagnostics['no_consumers'] = True
      diagnostics['new_control_value'] = control_range[0]
      return diagnostics

    actual_value = plc.read_by_name(actual_value_name)

    error = actual_value - set_point
    I_error = ema(I_error, error, dt, integration_decay_factor)
    ema_D_decay_factor = 0.5 ** (1/5)
    D_error = ema(D_error, fd1(last_value, error, dt), dt, ema_D_decay_factor)

    with parameter_lock:
      P = Kp * error
      I = Ki * I_error
      D = Kd * D_error

    last_value = error
    control_output = P + I + D

    new_control_value = control_output * dt + last_control if dt else last_control
    new_control_value = max(control_range[0], min(control_range[1], new_control_value))

    diagnostics |= {
      'actual_value': actual_value,
      'error': error,
      'I_error': I_error,
      'D_error': D_error,
      'P': P,
      'I': I,
      'D': D,
      'control_output': control_output,
      'new_control_value': new_control_value
    }

    if new_control_value <= control_range[0] / 2:
      plc.write_by_name(control_onoff_name, CONTROL_OFF)
      plc.write_by_name(control_value_name, 0)
    else:
      plc.write_by_name(control_onoff_name, CONTROL_ON)
      plc.write_by_name(control_value_name, max(new_control_value, 0))
    last_control = new_control_value

  except Exception as e:
    diagnostics['exception'] = repr(e)
    print(e)

  return diagnostics

def main(stop_requested):
  while not stop_requested():
    diagnostics = control_loop()
    for item in diagnostics.values():
      print('%0.2f ' % item if item is not None else '- ', end='')
    print(flush=True)

    try:
      time.sleep(5)
    except:
      break
  return 0

load_parameters()

if __name__ == '__main__':
  exit(main(lambda: False))


