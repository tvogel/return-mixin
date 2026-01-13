import control

control_bwk_name = 'PRG_WV.FB_Brenner.BWS.iStellung'

class BWK:
  def __init__(self, plc):
    self.plc = plc
    self.control = None

  def read(self):
    self.control = self.plc.read_by_name(control_bwk_name)

  def diagnostics(self):
    return {
      'control': control.control_str(self.control),
    }

  def set_control(self, new_control):
    if (self.control == new_control):
      return False
    self.plc.write_by_name(control_bwk_name, new_control)
    self.control = new_control
    return True

