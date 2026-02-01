#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import asyncio
from pid import PID
from base_control_module import BaseControlModule
from pump_pwm import PumpPWM
from dotenv import load_dotenv

circulation_value_name = 'PRG_HE.FB_TWW.FB_Zirkulationstemp.fOut'
control_value_name = 'PRG_HE.FB_TWW.FB_Ladepumpe.FB_BWS_Sollwert.FB_PmSw.fWert'
control_bws_name = 'PRG_HE.FB_TWW.FB_Ladepumpe.BWS.iStellung'

load_dotenv()

class Tww11(BaseControlModule):
  # Instance variable for MQTT callback
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.21.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='tww_11_params.json'
    )
    self.set_point = 56 # degrees
    self.pump_pwm = PumpPWM(self.plc, control_bws_name, control_value_name)
    self.last_update = None
    self.pid = PID(
      Kp = 1 / 60,
      Ki = 1 / 60,
      Kd = 0 / 60,
      integration_decay_factor = 0.5 ** (1/60)
    )

  def _set_module_parameters(self, params):
    self.set_point = params.get('circulation_set_point', self.set_point)
    self.pid.set_parameters(params.get('circulation_pid', self.pid.parameters()))
    self.pump_pwm.set_parameters(params.get('pump', self.pump_pwm.parameters()))

  def _get_module_parameters(self):
    return {
      'circulation_set_point': self.set_point,
      'circulation_pid': self.pid.parameters(),
      'pump': self.pump_pwm.parameters(),
    }

  def _control_action(self, now):
    diagnostics = {}
    dt = (now - self.last_update).total_seconds() if self.last_update else None
    self.last_update = now

    actual_value = self.plc.read_by_name(circulation_value_name)
    control_output = self.pid.update(self.set_point - actual_value, dt)

    diagnostics |= {
      'pump': self.pump_pwm.update(now, control_output * dt if dt else 0)
    }

    diagnostics |= {
      'dt': dt,
      'circulation': {
        'actual': actual_value,
        'error': self.pid.error,
        'I_error': self.pid.I_error,
        'D_error': self.pid.D_error,
        'P': self.pid.P,
        'I': self.pid.I,
        'D': self.pid.D,
        'control': control_output,
      },
      'new_control_value': self.pump_pwm.control
    }
    return diagnostics

tww_11 = Tww11()

async def main(stop_requested):
  tww_11.enabled = True
  while not stop_requested():
    diagnostics = tww_11.control_loop()
    print(diagnostics, flush=True)
    print(flush=True)
    try:
      await asyncio.sleep(5)
    except:
      break
  return 0

tww_11.load_parameters()

if __name__ == '__main__':
  asyncio.run(main(lambda: False))
