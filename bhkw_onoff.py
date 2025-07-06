#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyads
import datetime
import time
from suntimes import SunTimes
import control
from pk import PK
from buffer_tank import BufferTank
from base_control_module import BaseControlModule

latitude = 52.371582
longitude = 12.932913
altitude = 31

control_bhkw_name = 'PRG_WV.FB_BHKW.BWS.iStellung'

def solar_is_available(now = None, offset = datetime.timedelta(hours=2)):
  if now is None:
    now = datetime.datetime.now()
  sun = SunTimes(longitude, latitude, altitude)
  now = now.astimezone()
  sunrise = sun.riselocal(now)
  sunset = sun.setlocal(now)
  return now - sunrise > offset and sunset - now > offset

class BhkwOnOff(BaseControlModule):
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.21.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='bhkw_onoff_params.json'
    )
    self.buffer_tank = BufferTank(self.plc, 64, 58)
    self.last_update = None

  def _set_module_parameters(self, params):
    self.buffer_tank.set_parameters(params)

  def _get_module_parameters(self):
    return self.buffer_tank.parameters()

  def determine_control_value(self, current, solar_available, pk_available):
    #if not solar_available:
    #  return control.ON
    if pk_available:
      return control.OFF
    if (buffer_tank_control := self.buffer_tank.get_control()) is not None:
      return buffer_tank_control
    return current

  def _control_action(self, now):
    diagnostics = {}
    dt = (now - self.last_update).total_seconds() if self.last_update else None
    self.last_update = now

    self.buffer_tank.update(dt)
    diagnostics |= self.buffer_tank.diagnostics()

    solar_available = solar_is_available(now)
    diagnostics['solar_available'] = solar_available

    pk = PK(self.plc)
    pk.read()
    diagnostics['pk'] = pk.diagnostics()

    current_bhkw = control.invert(self.plc.read_by_name(control_bhkw_name))
    diagnostics['bhkw'] = control.control_str(current_bhkw)
    new_bhkw = self.determine_control_value(current_bhkw, solar_available, pk.is_available())

    if current_bhkw != new_bhkw:
      self.plc.write_by_name(control_bhkw_name, control.invert(new_bhkw))
      diagnostics['control_bhkw'] = control.control_str(new_bhkw)
      return diagnostics

    diagnostics['idle'] = True
    return diagnostics

bhkw_onoff = BhkwOnOff()

def main(stop_requested):
  while not stop_requested():
    diagnostics = bhkw_onoff.control_loop()
    print(diagnostics.pop('timestamp'), end=' ')
    print(diagnostics, flush=True)

    try:
      time.sleep(5)
    except:
      break
  return 0

bhkw_onoff.load_parameters()

if __name__ == '__main__':
  exit(main(lambda: False))


