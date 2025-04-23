AUTO = 1
OFF = 2
ON = 3
FAILURE = 10

def control_str(control):
  return {AUTO: 'auto', OFF: 'off', ON: 'on', FAILURE: 'failure'}.get(control, control)

def invert(control):
  if control == ON:
    return OFF
  if control == OFF:
    return ON
  return control
