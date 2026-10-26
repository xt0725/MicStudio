"""MicStudio — local mono voice processor, 48 kHz / 480 samples."""
import ctypes
from dataclasses import dataclass
import numpy as np
from scipy.signal import butter, sosfilt

@dataclass(frozen=True)
class Settings:
    gain: float = 0
    gate: float = -48
    threshold: float = -18
    ratio: float = 3
    bass: float = 0
    presence: float = 0
    highpass: bool = True
    ai: bool = False
    bypass: bool = False
    mute: bool = False

class RNNoise:
    def __init__(self, path):
        self.lib = ctypes.CDLL(str(path))
        p = ctypes.POINTER(ctypes.c_float)
        self.lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_create.restype = ctypes.c_void_p
        self.lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, p, p]
        self.lib.rnnoise_process_frame.restype = ctypes.c_float
        self.lib.rnnoise_get_frame_size.restype = ctypes.c_int
        if self.lib.rnnoise_get_frame_size() != 480:
            raise RuntimeError('RNNoise doit utiliser des blocs de 480 échantillons.')
        self.state = self.lib.rnnoise_create(None)
        if not self.state:
            raise RuntimeError('Initialisation RNNoise impossible.')
    def process(self, x):
        y = np.ascontiguousarray(x * 32768, dtype=np.float32)
        p = y.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self.lib.rnnoise_process_frame(self.state, p, p)
        return y / 32768
    def close(self):
        if self.state:
            self.lib.rnnoise_destroy(self.state)
            self.state = None

class Processor:
    def __init__(self, ai=None):
        self.ai = ai
        self.hp = butter(2, 80, 'highpass', fs=48000, output='sos')
        self.low = butter(2, 180, 'lowpass', fs=48000, output='sos')
        self.mid = butter(2, [2000, 5000], 'bandpass', fs=48000, output='sos')
        self.reset()
    def reset(self):
        self.states = [np.zeros((len(s), 2)) for s in (self.hp, self.low, self.mid)]
        self.gate_gain = 0.0
        self.comp_gain = 1.0
        self.input_db = self.output_db = -90.0
    def process(self, x, s):
        x = np.nan_to_num(np.asarray(x, dtype=np.float32), nan=0, posinf=0, neginf=0)
        self.input_db = float(20*np.log10(max(np.sqrt(np.mean(x*x)), 1e-9)))
        if s.mute:
            self.output_db = -90
            return np.zeros_like(x)
        if s.bypass:
            y = np.clip(x, -.98, .98)
        else:
            y = x * 10**(s.gain/20)
            filtered, self.states[0] = sosfilt(self.hp, y, zi=self.states[0])
            if s.highpass:
                y = filtered
            if s.ai and self.ai:
                y = self.ai.process(y)
            lo, self.states[1] = sosfilt(self.low, y, zi=self.states[1])
            mid, self.states[2] = sosfilt(self.mid, y, zi=self.states[2])
            y = y + lo*(10**(s.bass/20)-1) + mid*(10**(s.presence/20)-1)
            # Block envelope: fast opening, slow closure; 10ms blocks.
            db = float(20*np.log10(max(np.sqrt(np.mean(y*y)), 1e-9)))
            target = 1.0 if db > s.gate else 0.0
            old = self.gate_gain
            a = .15 if target > old else .94
            self.gate_gain = a*old+(1-a)*target
            y *= np.linspace(old, self.gate_gain, len(y))
            reduction = max(0, db-s.threshold)*(1-1/max(1, s.ratio))
            target = 10**(-reduction/20)
            old = self.comp_gain
            a = .3 if target < old else .94
            self.comp_gain = a*old+(1-a)*target
            y *= np.linspace(old, self.comp_gain, len(y))
            y = np.clip(y, -.98, .98)
        self.output_db = float(20*np.log10(max(np.sqrt(np.mean(y*y)), 1e-9)))
        return np.asarray(y, dtype=np.float32)
