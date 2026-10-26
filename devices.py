"""Active WASAPI endpoints only: no MME/DirectSound duplicate lists."""
from dataclasses import dataclass
import sounddevice as sd

VIRTUAL_WORDS=('cable','voicemeeter','sonar','micstudio','virtual','vb-audio')
BT_WORDS=('bluetooth','airpods','hands-free','hands free','bth','buds','wh-','wf-')
@dataclass(frozen=True)
class Device:
    id:int
    name:str
    capture:bool
    render:bool
    virtual:bool
    bluetooth:bool
    channels:int
    rate:float

def inventory(bluetooth_only=False):
    hosts=sd.query_hostapis()
    wasapi={i for i,h in enumerate(hosts) if 'WASAPI' in h['name'].upper()}
    devices=[]
    for i,d in enumerate(sd.query_devices()):
        if wasapi and d['hostapi'] not in wasapi:
            continue
        name=d['name'].strip()
        low=name.casefold()
        virtual=any(w in low for w in VIRTUAL_WORDS)
        bluetooth=any(w in low for w in BT_WORDS)
        if bluetooth_only and not bluetooth and not virtual:
            continue
        devices.append(Device(i,name,d['max_input_channels']>0,d['max_output_channels']>0,
            virtual,bluetooth,max(d['max_input_channels'],d['max_output_channels']),d['default_samplerate']))
    return devices

def wasapi_settings(device):
    d=sd.query_devices(device)
    host=sd.query_hostapis(d['hostapi'])['name']
    if 'WASAPI' in host.upper():
        return sd.WasapiSettings(auto_convert=True)
    return None
