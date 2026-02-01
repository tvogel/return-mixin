from ema import EMA
from op import FD1

class PID:
  def __init__(self, Kp, Ki, Kd, integration_decay_factor):
    self.Kp = Kp
    self.Ki = Ki
    self.Kd = Kd
    self.op_I = EMA(integration_decay_factor)
    self.op_D = FD1()
    self.error = None
    self.I_error = None
    self.D_error = None
    self.P = None
    self.I = None
    self.D = None

  def update(self, error, dt):
    self.error = error
    self.I_error = self.op_I.update(error, dt)
    self.D_error = self.op_D.update(error, dt)

    self.P = self.Kp * error
    self.I = self.Ki * self.I_error
    self.D = self.Kd * self.D_error

    return self.P + self.I + self.D

  def parameters(self):
    return {
      'Kp': self.Kp,
      'Ki': self.Ki,
      'Kd': self.Kd,
      'integration_decay_factor': self.op_I.decay_factor
    }

  def set_parameters(self, params):
    self.Kp = params.get('Kp', self.Kp)
    self.Ki = params.get('Ki', self.Ki)
    self.Kd = params.get('Kd', self.Kd)
    self.op_I.decay_factor = params.get('integration_decay_factor', self.op_I.decay_factor)
