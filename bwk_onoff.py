#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import datetime
import time
import control
from bwk import BWK
from pk import PK
from base_control_module import BaseControlModule
from distribution import any_consumer_on

actual_value_name = 'PRG_HE.FB_Haus_28_42_12_17_15_VL_Temp.fOut'

class EMA:
  def __init__(self, decay_factor):
    self.decay_factor = decay_factor
    self.last = None

  def update(self, value, dt):
    if self.last is None:
      self.last = value
      return self.last
    last_weight = self.decay_factor ** dt
    self.last = last_weight * self.last + (1 - last_weight) * value
    return self.last

class BwkOnOff(BaseControlModule):
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.21.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='bwk_onoff_params.json'
    )
    self.threshold = 60 # degrees
    self.auto_duration_minutes = 10

    self.last_update_dt = None
    self.value_ema = EMA(0.5 ** (1/60))  # 50% per minute
    self.auto_off_dt = None

  def _set_module_parameters(self, params):
    self.value_ema.decay_factor = params.get('decay_factor', self.value_ema.decay_factor)
    self.threshold = params.get('threshold', self.threshold)
    self.auto_duration_minutes = params.get('auto_duration_minutes', self.auto_duration_minutes)

  def _get_module_parameters(self):
    return {
      'decay_factor': self.value_ema.decay_factor,
      'threshold': self.threshold,
      'auto_duration_minutes': self.auto_duration_minutes
    }

  def _control_action(self, now):
    actual_value = self.plc.read_by_name(actual_value_name)
    bwk = BWK(self.plc)
    bwk.read()
    pk = PK(self.plc)
    pk.read()
    consumption = any_consumer_on(self.plc)

    dt = (now - self.last_update_dt).total_seconds() if self.last_update_dt else None
    self.last_update_dt = now
    if consumption or dt is None:
      self.value_ema.update(actual_value, dt)
    diagnostics = {
      'value': round(actual_value, 2),
      'value_ema': round(self.value_ema.last, 2),
      'bwk': bwk.diagnostics(),
      'consumption': consumption,
    }
    if self.auto_off_dt:
      diagnostics['auto_off'] = self.auto_off_dt.replace(microsecond=0).isoformat()

    if consumption and self.value_ema.last < self.threshold:
      bwk.set_control(control.ON)
      diagnostics['control_bwk'] = 'on'
      self.auto_off_dt = now + datetime.timedelta(minutes=self.auto_duration_minutes)
      diagnostics['auto_off'] = self.auto_off_dt.replace(microsecond=0).isoformat()
      return diagnostics

    if bwk.control == control.OFF:
      if self.auto_off_dt is not None:
        self.auto_off_dt = None
        diagnostics['auto_off'] = 'superceded'
        return diagnostics

    if bwk.control != control.OFF:
      if self.auto_off_dt is None:
        self.auto_off_dt = now + datetime.timedelta(minutes=self.auto_duration_minutes)
        diagnostics['auto_off'] = self.auto_off_dt.replace(microsecond=0).isoformat()
        return diagnostics
      if now >= self.auto_off_dt:
        self.auto_off_dt = None
        diagnostics['auto_off'] = 'expired'
        diagnostics['pk'] = pk.diagnostics()
        # if not pk.is_available():
        #   diagnostics['control_bwk'] = 'ignored (PK not available)'
        #   return diagnostics
        bwk.set_control(control.OFF)
        diagnostics['control_bwk'] = 'off'
        return diagnostics

    diagnostics['idle'] = True
    return diagnostics

bwk_onoff = BwkOnOff()

def main(stop_requested):
  bwk_onoff.enabled = True
  while not stop_requested():
    diagnostics = bwk_onoff.control_loop()
    print(diagnostics.pop('timestamp'), end=' ')
    print(diagnostics, flush=True)

    try:
      time.sleep(5)
    except:
      break
  return 0

bwk_onoff.load_parameters()

if __name__ == '__main__':
  exit(main(lambda: False))


