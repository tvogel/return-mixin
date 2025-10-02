import pyads

consumer_names = [
  'PRG_HE.FB_Hk_Haus_12_17_15.FB_Pumpe.bBetrieb',
  'PRG_HE.FB_Hk_Haus_28_42.FB_Pumpe.bBetrieb',
  'PRG_HE.FB_TWW.FB_Ladepumpe.bBetrieb'
]

def any_consumer_on(plc: pyads.Connection):
  return any(plc.read_list_by_name(consumer_names).values())
