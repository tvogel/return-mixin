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
from base_control_module import BaseControlModule
import control
import uuid
from dotenv import load_dotenv

actual_return_value_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_RL_Temp.fOut'
control_value_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.FB_BWS_Sollwert.FB_PmSw.fWert'
control_bws_name = 'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.BWS.iStellung'

load_dotenv()

MQTT_BROKER = 'mqtt.uferwerk.org'
MQTT_BROKER_PORT = 8883
MQTT_BROKER_SSL = True
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_TOPIC = 'metaview/metaview0'

# PWM parameters
DEFAULT_PWM_PERIOD = 300.0  # seconds, user-configurable (default: 5 minutes)

def on_connect(client, flags, rc, properties):
  print("Connected to MQTT broker")
  client.subscribe(MQTT_TOPIC)

def on_message(client, topic, payload, qos, properties):
  feed_121517.actual_circulation_mqtt(payload, properties)

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

def bounded(value, min_value, max_value):
  return max(min(value, max_value), min_value)

class Feed121517(BaseControlModule):
  # Instance variable for MQTT callback
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.21.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='feed_121517_params.json'
    )
    self.return_set_point = 52 # degrees
    self.circulation_set_point = 56 # degrees
    self.control_range = (-20, 100)  # Extended range: < 0 for PWM control
    self.min_if_no_circulation = 0.75 * self.control_range[0]
    self.pwm_period = DEFAULT_PWM_PERIOD
    self.last_control = None
    self.last_update = None
    self.pwm_state = {
      'cycle_start': None,
    }
    self.return_pid = PID(
      Kp = 1 / 60,
      Ki = 1 / 60,
      Kd = 0 / 60,
      integration_decay_factor = 0.5 ** (1/60)
    )
    self.circulation_pid = PID(
      Kp = 1 / 60,
      Ki = 1 / 60,
      Kd = 0 / 60,
      integration_decay_factor = 0.5 ** (1/60)
    )
    self.actual_circulation = None
    self.mqtt_client_id = f"feed_121517_{uuid.uuid4()}"

  async def setup_mqtt(self):
    self.mqtt_client = MQTTClient(self.mqtt_client_id)
    self.mqtt_client.on_connect = on_connect
    self.mqtt_client.on_message = on_message
    self.mqtt_client.set_auth_credentials(MQTT_USER, MQTT_PASSWORD)
    try:
      await self.mqtt_client.connect(MQTT_BROKER, MQTT_BROKER_PORT, MQTT_BROKER_SSL, keepalive=60)
    except Exception as e:
      print(f"Failed to connect to MQTT broker: {e}")


  def actual_circulation_mqtt(self, payload, properties):
    if properties['retain']:
      return

    try:
      value = json.loads(payload)
      self.actual_circulation = {
        "value": value,
        "timestamp": datetime.datetime.now()
      }
    except Exception as e:
      print(f"Failed to decode MQTT message: {e}")

  def _set_module_parameters(self, params):
    self.return_set_point = params.get('return_set_point', self.return_set_point)
    self.circulation_set_point = params.get('circulation_set_point', self.circulation_set_point)
    self.return_pid.set_parameters(params.get('return_pid', self.return_pid.parameters()))
    self.circulation_pid.set_parameters(params.get('circulation_pid', self.circulation_pid.parameters()))
    self.pwm_period = params.get('pwm_period', self.pwm_period)
    self.control_range[1] = params.get('max', self.control_range[1])
    self.min_if_no_circulation = params.get('min_if_no_circulation', self.min_if_no_circulation)

  def _get_module_parameters(self):
    return {
      'return_set_point': self.return_set_point,
      'circulation_set_point': self.circulation_set_point,
      'return_pid': self.return_pid.parameters(),
      'circulation_pid': self.circulation_pid.parameters(),
      'pwm_period': self.pwm_period,
      'max': self.control_range[1],
      'min_if_no_circulation': self.min_if_no_circulation
    }

  def _control_action(self, now):
    diagnostics = {}
    dt = (now - self.last_update).total_seconds() if self.last_update else None
    self.last_update = now
    plc = self.plc

    if self.last_control is None:
      self.last_control = self.control_range[0] if plc.read_by_name(control_bws_name) == control.OFF else plc.read_by_name(control_value_name)

    actual_return_value = plc.read_by_name(actual_return_value_name)
    control_output_return = self.return_pid.update(self.return_set_point - actual_return_value, dt)

    # Circulation from MQTT
    actual_circulation = self.actual_circulation
    control_output_circulation = None
    if actual_circulation and actual_circulation['timestamp']:
      if (now - actual_circulation['timestamp']).total_seconds() > 60:
        print("Actual circulation data is too old, skipping circulation control")
        self.actual_circulation = None
        actual_circulation = None
    if actual_circulation:
      control_output_circulation = self.circulation_pid.update(self.circulation_set_point - actual_circulation['value'], dt)

    control_output = max((x for x in (control_output_return, control_output_circulation) if x is not None), default=0)

    current_control_value = plc.read_by_name(control_value_name)
    new_control_value = control_output * dt + self.last_control if dt else self.last_control
    new_control_value = bounded(new_control_value, *self.control_range)
    if not actual_circulation:
      new_control_value = bounded(new_control_value, self.min_if_no_circulation, self.control_range[1])
    self.last_control = new_control_value

    # PWM logic for (-20, 0)
    if new_control_value < 0:
      duty_cycle = 1.0 * (new_control_value + 20) / 20 + 0.0 # (0.0, 1)
      if self.pwm_state['cycle_start'] is None:
        self.pwm_state['cycle_start'] = now
      else:
        elapsed_total = (now - self.pwm_state['cycle_start']).total_seconds()
        if elapsed_total >= self.pwm_period:
          self.pwm_state['cycle_start'] = now - datetime.timedelta(seconds=elapsed_total % self.pwm_period)
      elapsed = (now - self.pwm_state['cycle_start']).total_seconds()
      on_time = duty_cycle * self.pwm_period
      pwm_on = elapsed < on_time
      plc.write_by_name(control_value_name, 0)
      plc.write_by_name(control_bws_name, control.ON if pwm_on else control.OFF)
      diagnostics['pwm'] = {
        'duty_cycle': duty_cycle,
        'pwm_on': pwm_on,
        'elapsed': elapsed,
        'on_time': on_time,
        'period': self.pwm_period
      }
    else:
      plc.write_by_name(control_bws_name, control.ON)
      plc.write_by_name(control_value_name, new_control_value)

    diagnostics |= {
      'dt': dt,
      'return': {
        'actual': actual_return_value,
        'error': self.return_pid.error,
        'I_error': self.return_pid.I_error,
        'D_error': self.return_pid.D_error,
        'P': self.return_pid.P,
        'I': self.return_pid.I,
        'D': self.return_pid.D,
        'control': control_output_return,
      },
      'circulation': {
        'actual': actual_circulation['value'] if actual_circulation else None,
        'error': self.circulation_pid.error,
        'I_error': self.circulation_pid.I_error,
        'D_error': self.circulation_pid.D_error,
        'P': self.circulation_pid.P,
        'I': self.circulation_pid.I,
        'D': self.circulation_pid.D,
        'control': control_output_circulation,
      },
      'control_output': control_output,
      'new_control_value': new_control_value
    }
    return diagnostics

feed_121517 = Feed121517()

async def main(stop_requested):
  feed_121517.enabled = True
  await feed_121517.setup_mqtt()
  while not stop_requested():
    diagnostics = feed_121517.control_loop()
    print(diagnostics, flush=True)
    print(flush=True)
    try:
      await asyncio.sleep(5)
    except:
      break
  return 0

feed_121517.load_parameters()

if __name__ == '__main__':
  asyncio.run(main(lambda: False))
