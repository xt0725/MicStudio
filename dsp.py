"""48 kHz voice chain. RNNoise v0.1 ABI, compiled from pinned Xiph sources."""
import ctypes
import math
from dataclasses import dataclass, fields
import numpy as np
from scipy.signal import butter, sosfilt, lfilter

RATE = 48000
BLOCK = 480
EQ_FREQS = (80, 160, 315, 630, 1250, 2500, 5000, 10000)

def dbfs(x):
    return float(20*np.log10(max(float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))), 1e-9)))

def amp(db):
    return 10**(db/20)

@dataclass(frozen=True)
class Settings:
    gain: float = 0
    gate: float = -50
    gate_attack: float = 5
    gate_release: float = 160
    gate_hold: float = 120
    threshold: float = -20
    ratio: float = 3
    comp_attack: float = 8
    comp_release: float = 120
    makeup: float = 2
    ceiling: float = -1
    highpass: bool = True
    highpass_hz: float = 80
    ai: bool = True
    ai_strength: float = 100
    deesser: float = 25
    eq: tuple = (0, 0, 0, 0, 0, 0, 0, 0)
    bypass: bool = False
    mute: bool = False

LIMITS = {'gain':(-24,24), 'gate':(-90,-10), 'gate_attack':(1,100),
    'gate_release':(20,1000), 'gate_hold':(0,1000), 'threshold':(-50,0),
    'ratio':(1,12), 'comp_attack':(1,100), 'comp_release':(20,1000),
    'makeup':(0,18), 'ceiling':(-12,0), 'highpass_hz':(30,250),
    'ai_strength':(0,100), 'deesser':(0,100)}

def validated_settings(data):
    if not isinstance(data,dict) or set(data)-{f.name for f in fields(Settings)}:
        raise ValueError('Profil inconnu.')
    for k,v in data.items():
        if k in LIMITS:
            lo,hi = LIMITS[k]
            if type(v) not in (int,float) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError('Valeur invalide : '+k)
        elif k == 'eq':
            if not isinstance(v,(list,tuple)) or len(v)!=8 or any(type(n) not in (int,float) or not math.isfinite(n) or not -12<=n<=12 for n in v):
                raise ValueError('Égaliseur invalide.')
        elif type(v) is not bool:
            raise ValueError('Option invalide : '+k)
    return Settings(**{**data, 'eq':tuple(data.get('eq',Settings().eq))})

class RNNoise:
    def __init__(self,path):
        self.lib=ctypes.CDLL(str(path))
        ptr=ctypes.POINTER(ctypes.c_float)
        # Pinned v0.1 API has no model argument; model is embedded in the DLL.
        self.lib.rnnoise_create.argtypes=[]
        self.lib.rnnoise_create.restype=ctypes.c_void_p
        self.lib.rnnoise_destroy.argtypes=[ctypes.c_void_p]
        self.lib.rnnoise_process_frame.argtypes=[ctypes.c_void_p,ptr,ptr]
        self.lib.rnnoise_process_frame.restype=ctypes.c_float
        self.state=None
        self.reset()
    def reset(self):
        self.close()
        self.state=self.lib.rnnoise_create()
        if not self.state:
            raise RuntimeError('RNNoise : allocation impossible.')
        self.probability=0.0
    def process(self,x):
        if len(x)!=BLOCK:
            raise ValueError('RNNoise attend 480 échantillons.')
        y=np.ascontiguousarray(x*32768,dtype=np.float32)
        ptr=y.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self.probability=float(self.lib.rnnoise_process_frame(self.state,ptr,ptr))
        return y/32768
    def close(self):
        if self.state:
            self.lib.rnnoise_destroy(self.state)
            self.state=None

def peak_filter(freq,gain,q=1.15):
    A=10**(gain/40)
    w=2*np.pi*freq/RATE
    alpha=np.sin(w)/(2*q)
    a0=1+alpha/A
    return np.array([1+alpha*A,-2*np.cos(w),1-alpha*A])/a0, np.array([1,-2*np.cos(w)/a0,(1-alpha/A)/a0])

class Processor:
    def __init__(self,ai=None):
        self.ai=ai
        self.design=None
        self.configure(Settings())
        self.reset()
    def configure(self,s):
        key=(s.highpass_hz,tuple(s.eq))
        if key==self.design:
            return
        self.design=key
        self.hp=butter(2,s.highpass_hz,'highpass',fs=RATE,output='sos')
        self.ess=butter(2,[4500,11000],'bandpass',fs=RATE,output='sos')
        self.eq_filters=[peak_filter(f,g) for f,g in zip(EQ_FREQS,s.eq)]
        self.hp_state=np.zeros((len(self.hp),2))
        self.ess_state=np.zeros((len(self.ess),2))
        self.eq_state=[np.zeros(2) for _ in EQ_FREQS]
    def reset(self):
        self.hp_state=np.zeros((len(self.hp),2))
        self.ess_state=np.zeros((len(self.ess),2))
        self.eq_state=[np.zeros(2) for _ in EQ_FREQS]
        self.gate_gain=0.0
        self.comp_gain=1.0
        self.hold=0
        self.input_db=self.output_db=-90.0
        self.reduction=0.0
        self.clipping=False
        self.dry_delay=np.zeros(BLOCK,dtype=np.float32)
        if self.ai:
            self.ai.reset()
    @staticmethod
    def envelope(old,target,ms):
        a=math.exp(-10/max(ms,1))
        return a*old+(1-a)*target
    def process(self,x,s):
        self.configure(s)
        x=np.nan_to_num(np.asarray(x,dtype=np.float32),nan=0,posinf=0,neginf=0)
        self.input_db=dbfs(x)
        self.clipping=bool(np.max(np.abs(x))>=.999)
        if s.mute:
            self.output_db=-90
            return np.zeros_like(x)
        if s.bypass:
            y=x.copy()
        else:
            y=x*amp(s.gain)
            hp,self.hp_state=sosfilt(self.hp,y,zi=self.hp_state)
            if s.highpass:
                y=hp
            if s.ai and self.ai:
                dry=y.copy()
                wet=self.ai.process(y)
                mix=s.ai_strength/100
                # RNNoise includes one frame of analysis delay.
                y=wet*mix+self.dry_delay*(1-mix)
                self.dry_delay=dry
            for i,(b,a) in enumerate(self.eq_filters):
                y,self.eq_state[i]=lfilter(b,a,y,zi=self.eq_state[i])
            ess,self.ess_state=sosfilt(self.ess,y,zi=self.ess_state)
            ess_ratio=min(1.0,amp(dbfs(ess)-dbfs(y)))
            y=y-ess*(s.deesser/100)*max(0,(ess_ratio-.2)/.8)*.8
            level=dbfs(y)
            if level>s.gate:
                self.hold=s.gate_hold
                target=1.0
            elif self.hold>0:
                self.hold=max(0,self.hold-10)
                target=1.0
            else:
                target=0.0
            old=self.gate_gain
            self.gate_gain=self.envelope(old,target,s.gate_attack if target>old else s.gate_release)
            y*=np.linspace(old,self.gate_gain,len(y))
            self.reduction=max(0,level-s.threshold)*(1-1/s.ratio)
            target=amp(-self.reduction)
            old=self.comp_gain
            self.comp_gain=self.envelope(old,target,s.comp_attack if target<old else s.comp_release)
            y*=np.linspace(old,self.comp_gain,len(y))*amp(s.makeup)
        # Peak limiter with immediate block gain and clipping as final backstop.
        ceiling=amp(s.ceiling)
        peak=max(float(np.max(np.abs(y))),1e-9)
        y=np.clip(y*min(1,ceiling/peak),-ceiling,ceiling)
        self.output_db=dbfs(y)
        return np.asarray(y,dtype=np.float32)
