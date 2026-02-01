import datetime

class PWM:
  def __init__(self, period = 300):
    self.period = period
    self.control = 0
    self.cycle_start = None

  def parameters(self):
    return {
      'period': self.period
    }

  def set_parameters(self, params):
    self.period = params.get('period', self.period)

  def set_control(self, control):
    self.control = control

  def update(self, now):
    if self.cycle_start is None:
      self.cycle_start = now
    else:
      elapsed = (now - self.cycle_start).total_seconds()
      self.cycle_start = now - datetime.timedelta(seconds = elapsed % self.period)
    elapsed = (now - self.cycle_start).total_seconds()
    on_time = self.control * self.period
    on = elapsed < on_time

    return {
      'control': self.control,
      'on': on,
      'elapsed': elapsed,
      'on_time': on_time,
      'period': self.period
    }
