class EMA:
  def __init__(self, decay_factor):
    self.decay_factor = decay_factor
    self.last = None

  def update(self, value, dt):
    if self.last is None:
      self.last = value
      return self.last
    last_weight = self.decay_factor ** dt
    self.last = last_weight * self.last + (1 - last_weight) * value
    return self.last

  def parameters(self):
    return {
      'decay_factor': self.decay_factor
    }

  def set_parameters(self, params):
    self.decay_factor = params.get('decay_factor', self.decay_factor)
