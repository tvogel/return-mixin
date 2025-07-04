import datetime

class MinMaxValue:
  STATE_OK = 0
  STATE_MIN_ALARM = 12
  STATE_MAX_ALARM = 13

  def state_to_string(state):
    if state == MinMaxValue.STATE_OK:
      return 'OK'
    elif state == MinMaxValue.STATE_MIN_ALARM:
      return 'MIN_ALARM'
    elif state == MinMaxValue.STATE_MAX_ALARM:
      return 'MAX_ALARM'
    else:
      return f'UNKNOWN({state})'

  def __init__(self, plc, name):
    self.plc = plc
    self.name = name
    self.value_name = f'{name}.fOut'
    self.threshold_min_name = f'{name}.fThresholdMin'
    self.threshold_max_name = f'{name}.fThresholdMax'
    self.threshold_delta_name = f'{name}.fThresholdDelta'
    self.alert_name = f'{name}.bQStoerung'
    self.state_name = f'{name}.iQState'
    self.alert_min_name = f'{name}.bQMin'
    self.alert_max_name = f'{name}.bQMax'
    self.reset_name = f'{name}.bQuit'
    self.alert_state_left_timestamp = None
    self.auto_reset_seconds = None

  def set_parameters(self, params):
    self.auto_reset_seconds = params.get('auto_reset_seconds', self.auto_reset_seconds)

  def parameters(self):
    return {
      'auto_reset_seconds': self.auto_reset_seconds,
    }

  def update(self):
    state = self.plc.read_list_by_name([
      self.value_name,
      self.threshold_min_name,
      self.threshold_max_name,
      self.threshold_delta_name,
      self.alert_name,
      self.state_name,
      self.alert_min_name,
      self.alert_max_name,
    ])

    diagnostics = {
      'value': state[self.value_name],
      'threshold_min': state[self.threshold_min_name],
      'threshold_max': state[self.threshold_max_name],
      'threshold_delta': state[self.threshold_delta_name],
      'alert': state[self.alert_name],
      'state': MinMaxValue.state_to_string(state[self.state_name]),
      'alert_min': state[self.alert_min_name],
      'alert_max': state[self.alert_max_name],
    }

    if state[self.alert_min_name] or state[self.alert_max_name]:
      # alert state still current
      self.alert_state_left_timestamp = None
      return diagnostics | { 'action': 'wait' }

    if self.alert_state_left_timestamp is None:
      if state[self.state_name] == self.STATE_MAX_ALARM and not state[self.alert_max_name] \
        or state[self.state_name] == self.STATE_MIN_ALARM and not state[self.alert_min_name]:
          self.alert_state_left_timestamp = datetime.datetime.now()

    if self.alert_state_left_timestamp is not None:
      diagnostics['alert_state_left'] = (datetime.datetime.now() - self.alert_state_left_timestamp).total_seconds()
      diagnostics['auto_reset_seconds'] = self.auto_reset_seconds

    if self.auto_reset_seconds is not None and self.alert_state_left_timestamp is not None:
      now = datetime.datetime.now()
      if (now - self.alert_state_left_timestamp).total_seconds() >= self.auto_reset_seconds:
        # reset alert state
        # self.plc.write_by_name(self.reset_name, True)
        self.plc.write_by_name(self.state_name, self.STATE_OK)
        self.alert_state_left_timestamp = None
        return diagnostics | { 'action': 'reset' }

    return diagnostics | { 'action': (self.alert_state_left_timestamp and self.auto_reset_seconds) and 'delay' or 'idle' }
