#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import time
import control
from pk import PK
from buffer_tank import BufferTank
from base_control_module import BaseControlModule


class PkOnOff(BaseControlModule):
  def __init__(self):
    super().__init__(
      plc_ams_net_id="192.168.35.21.1.1",
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename="pk_onoff_params.json",
    )
    self.buffer_tank = BufferTank(self.plc, 64, 58)
    self.last_update_dt = None

  def _set_module_parameters(self, params):
    self.buffer_tank.set_parameters(params)

  def _get_module_parameters(self):
    return self.buffer_tank.parameters()

  def _control_action(self, now):
    diagnostics = {}
    dt = (
      (now - self.last_update_dt).total_seconds()
      if self.last_update_dt
      else None
    )
    self.last_update_dt = now

    pk = PK(self.plc)
    pk.read()

    self.buffer_tank.update(dt)

    diagnostics |= self.buffer_tank.diagnostics()
    diagnostics["pk"] = pk.diagnostics()

    new_control_pk = pk.control

    if not pk.is_available():
      new_control_pk = control.OFF
    elif (buffer_tank_control := self.buffer_tank.get_control()) is not None:
      new_control_pk = buffer_tank_control

    if pk.set_control(new_control_pk):
      diagnostics["control"] = control.control_str(new_control_pk)
      return diagnostics

    diagnostics["idle"] = True
    return diagnostics

pk_onoff = PkOnOff()

def main(stop_requested):
  pk_onoff.enabled = True
  while not stop_requested():
    diagnostics = pk_onoff.control_loop()
    print(diagnostics.pop("timestamp"), end=" ")
    print(diagnostics, flush=True)
    try:
      time.sleep(5)
    except:
      break
  return 0


pk_onoff.load_parameters()

if __name__ == "__main__":
  exit(main(lambda: False))
