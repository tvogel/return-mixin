#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import time
from base_control_module import BaseControlModule
from ema import EMA
from distribution import any_consumer_on

actual_value_name = 'PRG_HE.FB_Haus_28_42_12_17_15_VL_Temp.fOut'
control_value_name = 'PRG_HE.FB_Zusatzspeicher.FB_Speicherladeset_Pumpe.FB_BWS_Sollwert.FB_PmSw.fWert'
control_onoff_name = 'PRG_HE.FB_Zusatzspeicher.FB_Speicherladeset_Pumpe.BWS.iStellung'

CONTROL_OFF = 2
CONTROL_ON = 3

def fd1(last, value, dt):
  if last is None or dt is None:
    return 0
  return (value - last) / dt

class ReturnMixin(BaseControlModule):
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.21.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='return_mixin_params.json'
    )
    self.set_point = 63.5
    self.Kp = 6 / 60 # percent per second per degree
    self.Ki = 3 / 60 # percent per second per long-term degree
    self.Kd = 900 / 60 # percent per second per degree change per second
    self.control_range = (-30, 100)
    self.last_value = None
    self.last_control = None
    self.last_update = None
    self.I_error = None
    self.D_error = None
    self.I_ema = EMA(0.5 ** (1/300))  # 50% per five minutes
    self.D_ema = EMA(0.5 ** (1/5)) # 50% per 5 seconds

  def _set_module_parameters(self, params):
    self.Kp = params.get('Kp', self.Kp)
    self.Ki = params.get('Ki', self.Ki)
    self.Kd = params.get('Kd', self.Kd)
    self.set_point = params.get('set_point', self.set_point)
    self.control_range = (-params.get('off_range', -self.control_range[0]), self.control_range[1])
    self.I_ema.decay_factor = params.get('decay_factor', self.I_ema.decay_factor)

  def _get_module_parameters(self):
    return {
      'Kp': self.Kp,
      'Ki': self.Ki,
      'Kd': self.Kd,
      'set_point': self.set_point,
      'off_range': -self.control_range[0],
      'decay_factor': self.I_ema.decay_factor
    }

  def any_consumer_on(self):
    return any_consumer_on(self.plc)

  def _control_action(self, now):
    diagnostics = {}
    if self.last_control is None:
      self.last_control = self.plc.read_by_name(control_value_name) \
        if self.plc.read_by_name(control_onoff_name) == CONTROL_ON \
        else self.control_range[0]

    dt = (now - self.last_update).total_seconds() if self.last_update else None
    self.last_update = now
    diagnostics['dt'] = dt

    if not self.any_consumer_on():
      self.plc.write_by_name(control_onoff_name, CONTROL_OFF)
      self.plc.write_by_name(control_value_name, 0)
      diagnostics['no_consumers'] = True
      diagnostics['new_control_value'] = self.control_range[0]
      return diagnostics

    actual_value = self.plc.read_by_name(actual_value_name)
    error = actual_value - self.set_point
    I_error = self.I_ema.update(error, dt if dt else 0)
    D_error = self.D_ema.update(fd1(self.last_value, error, dt), dt if dt else 0)

    P = self.Kp * error
    I = self.Ki * I_error
    D = self.Kd * D_error

    self.last_value = error
    control_output = P + I + D

    new_control_value = control_output * dt + self.last_control if dt else self.last_control
    new_control_value = max(self.control_range[0], min(self.control_range[1], new_control_value))

    diagnostics.update({
      'actual_value': actual_value,
      'error': error,
      'I_error': I_error,
      'D_error': D_error,
      'P': P,
      'I': I,
      'D': D,
      'control_output': control_output,
      'new_control_value': new_control_value
    })

    if new_control_value <= self.control_range[0] / 2:
      self.plc.write_by_name(control_onoff_name, CONTROL_OFF)
      self.plc.write_by_name(control_value_name, 0)
    else:
      self.plc.write_by_name(control_onoff_name, CONTROL_ON)
      self.plc.write_by_name(control_value_name, max(new_control_value, 0))
    self.last_control = new_control_value

    return diagnostics

return_mixin = ReturnMixin()
return_mixin.load_parameters()

def main(stop_requested):
  return_mixin.enabled = True
  while not stop_requested():
    diagnostics = return_mixin.control_loop()
    for item in diagnostics.values():
      print('%0.2f ' % item if isinstance(item, (int, float)) else '- ', end='')
    print(flush=True)
    try:
      time.sleep(5)
    except:
      break
  return 0

if __name__ == '__main__':
  exit(main(lambda: False))


