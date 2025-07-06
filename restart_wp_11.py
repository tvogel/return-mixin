#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from re import S
import pyads
import datetime
import time
import threading
import json
import os
import control
from base_control_module import BaseControlModule
from min_max_value import MinMaxValue

class RestartWP11(BaseControlModule):
  def __init__(self):
    super().__init__(
      plc_ams_net_id='192.168.35.32.1.1',
      plc_ams_port=pyads.PORT_TC3PLC1,
      param_filename='restart_wp_11.json'
    )
    self.hotgas_temp = MinMaxValue(self.plc, 'PRG_HE.FB_Waermepumpe.FB_Heissgas_Temp')

  def _set_module_parameters(self, params):
    self.hotgas_temp.set_parameters(params.get('hotgas_temp', self.hotgas_temp.parameters()))

  def _get_module_parameters(self):
    return {'hotgas_temp': self.hotgas_temp.parameters()}

  def _control_action(self, now):
    return self.hotgas_temp.update()

def open_plc():
  global plc
  plc = pyads.Connection('192.168.35.32.1.1', pyads.PORT_TC3PLC1)
  plc.open()

open_plc()

hotgas_temp = MinMaxValue(plc, 'PRG_HE.FB_Waermepumpe.FB_Heissgas_Temp')

PARAMS_FILE = os.path.join(os.path.dirname(__file__), 'restart_wp_11.json')

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

enabled = True

restart_wp_11 = RestartWP11()

def set_parameters(params):
  restart_wp_11.set_parameters(params)

def get_parameters():
  return restart_wp_11.get_parameters()

def control_loop():
  return restart_wp_11.control_loop()

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


