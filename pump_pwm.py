from pwm import PWM
from op import bounded
import control

class PumpPWM:
  def __init__(self, plc, bws_name, value_name, pwm_range = -20):
    self.plc = plc
    self.bws_name = bws_name
    self.value_name = value_name
    self.pwm_range = pwm_range
    self.control_range = [pwm_range, 100]
    self.control = None
    self.pwm = PWM()

  def parameters(self):
    return {
      'min': self.control_range[0],
      'max': self.control_range[1],
      'pwm': self.pwm.parameters()
    }

  def set_parameters(self, params):
    self.control_range[0] = params.get('min', self.control_range[0])
    self.control_range[1] = params.get('max', self.control_range[1])
    self.pwm.set_parameters(params.get('pwm', self.pwm.parameters()))

  def set_control(self, control):
    self.control = control

  def update(self, now, control_delta):
    if self.control is None:
      state = self.plc.read_list_by_name([
        self.bws_name,
        self.value_name
      ])
      self.control = self.control_range[0] if state[self.bws_name] else state[self.value_name]

    self.control = self.control + control_delta
    self.control = bounded(self.control, *self.control_range)

    if self.control < 0:
      # PWM range
      self.pwm.set_control((self.control - self.pwm_range) / (-self.pwm_range))
      pwm_control = self.pwm.update(now)
      self.plc.write_list_by_name({
        self.bws_name: control.ON if pwm_control['on'] else control.OFF,
        self.value_name: 0
      })
      return { 'pwm': pwm_control }

    self.plc.write_list_by_name({
      self.bws_name: control.ON,
      self.value_name: self.control
    })

    return { 'speed': self.control }
