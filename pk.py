import control

control_name = 'PRG_WV.FB_Pelletkessel.BWS.iStellung'
available_name = 'PRG_WV.FB_Pelletkessel_AT_Gw.bQ'
stoerung_name = 'PRG_WV.FB_Pelletkessel.bStoerung'

class PK:
  def __init__(self, plc):
    self.plc = plc
    self.control = None
    self.available = None
    self.stoerung = None

  def read(self):
    self.control = self.plc.read_by_name(control_name)
    self.available = self.plc.read_by_name(available_name)
    self.stoerung = self.plc.read_by_name(stoerung_name)

  def diagnostics(self):
    return {
      'control': control.control_str(self.control),
      'available': self.available
    } | ({ 'stoerung': True } if self.stoerung else {})

  def set_control(self, new_control):
    if (self.control == new_control):
      return False
    self.plc.write_by_name(control_name, new_control)
    self.control = new_control
    return True

  def is_available(self):
    return self.available and not self.stoerung and self.control != control.FAILURE

