class FD1:
  def __init__(self):
    self.last = None

  def update(self, value, dt):
    if self.last is None:
      self.last = value
      return 0

    result = (value - self.last) / dt
    self.last = value
    return result

def bounded(value, min_value, max_value):
  return max(min(value, max_value), min_value)

