import control
from ema import EMA

on1_value_name = 'PRG_HE.FB_Speicher_1_Temp_oben.fOut'
on2_value_name = 'PRG_HE.FB_Speicher_2_Temp_oben.fOut'
off1_value_name = 'PRG_HE.FB_Speicher_1_Temp_unten.fOut'
off2_value_name = 'PRG_HE.FB_Speicher_2_Temp_unten.fOut'

class BufferTank:
  def __init__(self, plc, on_threshold, off_threshold):
    self.plc = plc
    self.on_threshold = on_threshold
    self.off_threshold = off_threshold

    self.on1_value = None
    self.on2_value = None
    self.off1_value = None
    self.off2_value = None

    self.on_value_ema = EMA(0.5 ** (1/60)) # 50% per minute
    self.off_value_ema = EMA(0.5 ** (1/60)) # 50% per minute

  def set_parameters(self, params):
    self.on_threshold = params.get('on_threshold', self.on_threshold)
    self.off_threshold = params.get('off_threshold', self.off_threshold)
    self.on_value_ema.set_parameters(params)
    self.off_value_ema.set_parameters(params)

  def parameters(self):
    return {
      'on_threshold': self.on_threshold,
      'off_threshold': self.off_threshold,
    } | self.on_value_ema.parameters()

  def read(self):
    self.on1_value = self.plc.read_by_name(on1_value_name)
    self.on2_value = self.plc.read_by_name(on2_value_name)
    self.off1_value = self.plc.read_by_name(off1_value_name)
    self.off2_value = self.plc.read_by_name(off2_value_name)

  def update(self, dt):
    self.read()
    self.on_value_ema.update(min(self.on1_value, self.on2_value), dt)
    self.off_value_ema.update(max(self.off1_value, self.off2_value), dt)

  def diagnostics(self):
    diagnostics = {}
    diagnostics['on_value_ema'] = round(self.on_value_ema.last, 2)
    diagnostics['off_value_ema'] = round(self.off_value_ema.last, 2)
    return diagnostics

  def get_control(self):
    if self.off_value_ema.last > self.off_threshold:
      return control.OFF
    if self.on_value_ema.last < self.on_threshold:
      return control.ON
    return None
