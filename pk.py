import control

control_name = 'PRG_WV.FB_Pelletkessel.BWS.iStellung'
ready_name = 'PRG_WV.FB_Pelletkessel.FB_Betriebsbereit.bQ'
at_gw_ok_name = 'PRG_WV.FB_Pelletkessel_AT_Gw.bQ'
stoerung_name = 'PRG_WV.FB_Pelletkessel.bStoerung'
power_name = 'PRG_WV.FB_Pelletkessel.FB_WMZ.FB_Power.VDB.Data_As_LReal'

class PK:
  def __init__(self, plc):
    self.plc = plc
    self.control = None
    self.ready = None
    self.at_gw_ok = None
    self.stoerung = None
    self.power = None

  def read(self):
    state = self.plc.read_list_by_name([
      control_name,
      ready_name,
      at_gw_ok_name,
      stoerung_name,
      power_name
    ])
    self.control = state[control_name]
    self.ready = state[ready_name]
    self.at_gw_ok = state[at_gw_ok_name]
    self.stoerung = state[stoerung_name]
    self.power = state[power_name]

  def diagnostics(self):
    return {
      'control': control.control_str(self.control),
      'ready': self.ready,
      'at_gw_ok': self.at_gw_ok
    } | ({ 'stoerung': True } if self.stoerung else {})

  def set_control(self, new_control):
    if (self.control == new_control):
      return False
    self.plc.write_by_name(control_name, new_control)
    self.control = new_control
    return True

  def is_available(self):
    return self.ready and self.at_gw_ok and not self.stoerung and self.control != control.FAILURE

  def is_producing(self):
    if not self.is_available():
      return False
    if self.control == control.OFF:
      return False
    return self.power is not None and self.power > 0

