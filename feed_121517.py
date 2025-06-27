#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import datetime
import time
import threading
import json
import os
import asyncio
from gmqtt import Client as MQTTClient
from ema import EMA

actual_return_value_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_RL_Temp.fOut'
control_value_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.FB_BWS_Sollwert.FB_PmSw.fWert'
control_bws_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.BWS.iStellung'

MQTT_BROKER = 'test.mosquitto.org'
MQTT_BROKER_PORT = 1883
MQTT_TOPIC = 'metaview/metaview0'

CONTROL_AUTO = 1
CONTROL_OFF = 2
CONTROL_ON = 3

return_set_point = 52 # degrees
circulation_set_point = 56 # degrees
control_range = (0, 100)

# Lock for PID parameters
parameter_lock = threading.Lock()

plc = pyads.Connection('192.168.35.21.1.1', pyads.PORT_TC3PLC1)
plc.open()

last_control = plc.read_by_name(control_value_name)
last_update = None

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'feed_121517_params.json')

mqtt_client = None
actual_circulation = None

def on_connect(client, flags, rc, properties):
  print("Connected to MQTT broker")

def on_message(client, topic, payload, qos, properties):
  global actual_circulation
  try:
    # print(f"Received message on topic {topic}: {payload}")
    actual_circulation = {
        "value": json.loads(payload),
        "timestamp": datetime.datetime.now()
    }
    # print(f"Received parameters: {actual_circulation}")
  except json.JSONDecodeError as e:
    print(f"Failed to decode MQTT message: {e}")

async def setup_mqtt():
  global mqtt_client
  mqtt_client = MQTTClient("feed_121517")
  mqtt_client.on_connect = on_connect
  mqtt_client.on_message = on_message
  await mqtt_client.connect(MQTT_BROKER, MQTT_BROKER_PORT)
  mqtt_client.subscribe(MQTT_TOPIC)

class FD1:
  def __init__(self):
    self.last = None

  def update(self, value, dt):
    if self.last is None:
      self.last = value
      return 0
    result = (value - self.last) / dt
    self.last = value
    return result

class PID:
  def __init__(self, Kp, Ki, Kd, integration_decay_factor):
    self.Kp = Kp
    self.Ki = Ki
    self.Kd = Kd
    self.op_I = EMA(integration_decay_factor)
    self.op_D = FD1()
    self.error = None
    self.I_error = None
    self.D_error = None
    self.P = None
    self.I = None
    self.D = None

  def update(self, error, dt):
    self.error = error
    self.I_error = self.op_I.update(error, dt)
    self.D_error = self.op_D.update(error, dt)

    self.P = self.Kp * error
    self.I = self.Ki * self.I_error
    self.D = self.Kd * self.D_error

    return self.P + self.I + self.D

  def parameters(self):
    return {
      'Kp': self.Kp,
      'Ki': self.Ki,
      'Kd': self.Kd,
      'integration_decay_factor': self.op_I.decay_factor
    }

  def set_parameters(self, params):
    self.Kp = params.get('Kp', self.Kp)
    self.Ki = params.get('Ki', self.Ki)
    self.Kd = params.get('Kd', self.Kd)
    self.op_I.decay_factor = params.get('integration_decay_factor', self.op_I.decay_factor)


return_pid = PID(
  Kp = 1 / 60, # percent per second per degree
  Ki = 1 / 60, # percent per second per long-term degree
  Kd = 0 / 60, # percent per second per degree change per second,
  integration_decay_factor = 0.5 ** (1/60) # 50% per minute
)

circulation_pid = PID(
  Kp = 1 / 60, # percent per second per degree
  Ki = 1 / 60, # percent per second per long-term degree
  Kd = 0 / 60, # percent per second per degree change per second,
  integration_decay_factor = 0.5 ** (1/60) # 50% per minute
)

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

enabled = True

def set_parameters(params):
  global return_set_point, circulation_set_point, return_pid, enabled
  with parameter_lock:
    enabled = params.get('enabled', enabled)
    return_set_point = params.get('return_set_point', return_set_point)
    circulation_set_point = params.get('circulation_set_point', circulation_set_point)
    return_pid.set_parameters(params.get('return_pid', return_pid.parameters()))
    circulation_pid.set_parameters(params.get('circulation_pid', circulation_pid.parameters()))
  save_parameters()

def get_parameters():
  with parameter_lock:
    return {
        'enabled': enabled,
        'return_set_point': return_set_point,
        'circulation_set_point': circulation_set_point,
        'return_pid': return_pid.parameters(),
        'circulation_pid': circulation_pid.parameters()
    }

def bounded(value, min_value, max_value):
  return max(min(value, max_value), min_value)

async def control_loop():
  global last_control, last_update, actual_circulation, enabled

  diagnostics = {}
  now = datetime.datetime.now()
  diagnostics['timestamp'] = now.replace(microsecond=0).isoformat()

  if not enabled:
    diagnostics['disabled'] = True
    return diagnostics

  dt = (now - last_update).total_seconds() if last_update else None
  last_update = now

  try:
    with parameter_lock:
      actual_return_value = plc.read_by_name(actual_return_value_name)
      control_output_return = return_pid.update(return_set_point - actual_return_value, dt)

      control_output_circulation = None
      if actual_circulation:
        control_output_circulation = circulation_pid.update(circulation_set_point - actual_circulation['value'], dt)

      control_output = max((x for x in (control_output_return, control_output_circulation) if x is not None), default=0)

      current_control_value = plc.read_by_name(control_value_name)
      new_control_value = control_output * dt + current_control_value if dt else current_control_value
      new_control_value = bounded(new_control_value, *control_range)

    diagnostics |= {
      'dt': dt,
      'return': {
        'actual': actual_return_value,
        'error': return_pid.error,
        'I_error': return_pid.I_error,
        'D_error': return_pid.D_error,
        'P': return_pid.P,
        'I': return_pid.I,
        'D': return_pid.D,
        'control': control_output_return,
      },
      'circulation': {
        'actual': actual_circulation['value'] if actual_circulation else None,
        'error': circulation_pid.error,
        'I_error': circulation_pid.I_error,
        'D_error': circulation_pid.D_error,
        'P': circulation_pid.P,
        'I': circulation_pid.I,
        'D': circulation_pid.D,
        'control': control_output_circulation,
      },
      'control_output': control_output,
      'new_control_value': new_control_value
    }

    if new_control_value != current_control_value:
      plc.write_by_name(control_bws_name, CONTROL_ON)
      plc.write_by_name(control_value_name, new_control_value)

  except Exception as e:
    print(e)

  return diagnostics

async def main(stop_requested):
  await setup_mqtt()
  while not stop_requested():
    diagnostics = await control_loop()
    print(diagnostics, flush=True)
    print(flush=True)

    try:
      await asyncio.sleep(5)
    except:
      break
  return 0

load_parameters()

if __name__ == '__main__':
  asyncio.run(main(lambda: False))
