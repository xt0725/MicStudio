"""MicStudio buses. Separate input/output clocks, bounded queues and drift compensation."""
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd
from devices import wasapi_settings
from dsp import Processor, Settings, RATE, BLOCK, dbfs, amp

class ElasticBuffer:
    """Bounded block queue. Output interpolation compensates independent audio clocks."""
    def __init__(self,max_blocks=24):
        self.queue=queue.Queue(maxsize=max_blocks)
        self.pending=np.zeros(0,dtype=np.float32)
        self.underruns=self.overruns=0
        self.primed=False
    def put(self,x):
        try:
            self.queue.put_nowait(np.asarray(x,dtype=np.float32).copy())
        except queue.Full:
            self.overruns+=1
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(np.asarray(x,dtype=np.float32).copy())
            except queue.Full:
                pass
    def read(self,n):
        while True:
            try:
                self.pending=np.concatenate((self.pending,self.queue.get_nowait()))
            except queue.Empty:
                break
        if len(self.pending)>BLOCK*24:
            self.pending=self.pending[-BLOCK*6:]
            self.overruns+=1
        if not self.primed:
            if len(self.pending)<BLOCK*3:
                return np.zeros(n,dtype=np.float32)
            self.primed=True
        # Adjust by at most 1% per callback around a 30 ms target fill.
        delta=int(np.clip((len(self.pending)-n-BLOCK*3)*.005,-n*.01,n*.01))
        take=max(1,n+delta)
        if len(self.pending)<take:
            self.underruns+=1
            self.primed=False
            self.pending=np.zeros(0,dtype=np.float32)
            return np.zeros(n,dtype=np.float32)
        chunk=self.pending[:take]
        self.pending=self.pending[take:]
        if take==n:
            return chunk
        return np.interp(np.linspace(0,take-1,n),np.arange(take),chunk).astype(np.float32)

@dataclass(frozen=True)
class Strip:
    gain:float=0
    mute:bool=False
    solo:bool=False
    monitor:bool=True
    broadcast:bool=False

class AudioEngine:
    def __init__(self,ai=None):
        self.processor=Processor(ai)
        self.settings=Settings(ai=ai is not None)
        self.strips=(Strip(broadcast=True),Strip(),Strip(),Strip())
        self.monitor_volume=-9
        self.broadcast_volume=0
        self.monitor_enabled=False
        self.streams=[]
        self.outputs={}
        self.aux={}
        self.running=False
        self.error=''
        self.status_events=0
        self.levels=[-90.0]*4
        self.bus_levels=[-90.0,-90.0]
        self.wave=np.zeros(BLOCK,dtype=np.float32)
        self.spectrum=np.full(64,-90,dtype=np.float32)
        self.player=np.zeros(0,dtype=np.float32)
        self.player_position=0
        self.playing=False
        self.loop=False
        self.record_queue=queue.Queue(maxsize=300)
        self.recording=False
        self.record_thread=None
        self.record_error=''
        self.started_at=0
    def load_file(self,path):
        info=sf.info(path)
        if info.duration>60*20:
            raise ValueError('Choisissez un fichier de moins de 20 minutes.')
        data,rate=sf.read(path,dtype='float32',always_2d=True)
        data=np.mean(data,axis=1)
        if rate!=RATE:
            common=gcd(rate,RATE)
            data=resample_poly(data,RATE//common,rate//common).astype(np.float32)
        self.playing=False
        self.player=data
        self.player_position=0
    def _player_block(self,n):
        y=np.zeros(n,dtype=np.float32)
        if self.playing and len(self.player):
            pos=self.player_position
            count=min(n,len(self.player)-pos)
            y[:count]=self.player[pos:pos+count]
            self.player_position=pos+count
            if count<n or self.player_position==len(self.player):
                if self.loop:
                    self.player_position=0
                else:
                    self.playing=False
        return y
    def start(self,mic,monitor=None,broadcast=None,aux1=None,aux2=None,latency='high'):
        self.stop()
        if mic is None:
            raise ValueError('Choisissez un microphone connecté.')
        if monitor is None and broadcast is None:
            raise ValueError('Choisissez au moins un casque ou une sortie virtuelle.')
        if monitor is not None and monitor==broadcast:
            raise ValueError('Le casque et la sortie virtuelle doivent être différents.')
        if len({d for d in (mic,aux1,aux2) if d is not None}) != sum(d is not None for d in (mic,aux1,aux2)):
            raise ValueError('Une même entrée ne peut pas être ouverte deux fois.')
        self.error=''
        self.status_events=0
        self.outputs={}
        self.aux={}
        self.processor.reset()
        try:
            # Output consumers start first and initially emit silence.
            for bus,device in [('monitor',monitor),('broadcast',broadcast)]:
                if device is None:
                    continue
                buf=ElasticBuffer()
                self.outputs[bus]=buf
                channels=min(2,sd.query_devices(device)['max_output_channels'])
                def output(data,frames,t,status,b=buf):
                    data.fill(0)
                    try:
                        if status:
                            self.status_events+=1
                        data[:]=b.read(frames)[:,None]
                    except Exception as exc:
                        self.error=str(exc)
                        raise sd.CallbackAbort
                stream=sd.OutputStream(device=device,samplerate=RATE,blocksize=BLOCK,
                    channels=channels,dtype='float32',latency=latency,
                    extra_settings=wasapi_settings(device),callback=output)
                self.streams.append(stream)
                stream.start()
            for index,device in [(1,aux1),(2,aux2)]:
                if device is None:
                    continue
                buf=ElasticBuffer()
                self.aux[index]=buf
                def capture(data,frames,t,status,b=buf):
                    if status:
                        self.status_events+=1
                    b.put(np.mean(data,axis=1))
                channels=min(2,sd.query_devices(device)['max_input_channels'])
                stream=sd.InputStream(device=device,samplerate=RATE,blocksize=BLOCK,
                    channels=channels,dtype='float32',latency=latency,
                    extra_settings=wasapi_settings(device),callback=capture)
                self.streams.append(stream)
                stream.start()
            stream=sd.InputStream(device=mic,samplerate=RATE,blocksize=BLOCK,
                channels=1,dtype='float32',latency=latency,
                extra_settings=wasapi_settings(mic),callback=self._mix)
            self.streams.append(stream)
            stream.start()
            self.running=True
            self.started_at=time.monotonic()
        except Exception:
            self.stop()
            raise
    def _mix(self,data,frames,t,status):
        try:
            if status:
                self.status_events+=1
            if frames!=BLOCK:
                raise ValueError('Le moteur exige des blocs de 480 échantillons.')
            mic=self.processor.process(data[:,0],self.settings)
            sources=[mic]+[self.aux[i].read(frames) if i in self.aux else np.zeros(frames,dtype=np.float32) for i in (1,2)]+[self._player_block(frames)]
            monitor=np.zeros(frames,dtype=np.float32)
            broadcast=np.zeros(frames,dtype=np.float32)
            strips=self.strips
            any_solo=any(s.solo for s in strips)
            for i,(source,strip) in enumerate(zip(sources,strips)):
                source=source*amp(strip.gain)
                if strip.mute or (any_solo and not strip.solo):
                    source=np.zeros_like(source)
                self.levels[i]=dbfs(source)
                if strip.monitor:
                    monitor+=source
                if strip.broadcast:
                    broadcast+=source
            monitor*=amp(self.monitor_volume)
            broadcast*=amp(self.broadcast_volume)
            monitor=np.clip(monitor,-.98,.98)
            broadcast=np.clip(broadcast,-.98,.98)
            self.bus_levels=[dbfs(monitor),dbfs(broadcast)]
            self.wave=mic.copy()
            self.spectrum=20*np.log10(np.maximum(np.abs(np.fft.rfft(mic*np.hanning(frames)))/120,1e-6))
            if 'monitor' in self.outputs:
                self.outputs['monitor'].put(monitor if self.monitor_enabled else np.zeros_like(monitor))
            if 'broadcast' in self.outputs:
                self.outputs['broadcast'].put(broadcast)
            if self.recording:
                try:
                    self.record_queue.put_nowait(np.column_stack((data[:,0],mic)))
                except queue.Full:
                    self.record_error='Enregistrement arrêté : disque trop lent.'
                    self.recording=False
        except Exception as exc:
            self.error=str(exc)
            raise sd.CallbackAbort
    def start_recording(self,path):
        if not self.running:
            raise ValueError('Démarrez le moteur avant d’enregistrer.')
        self.stop_recording()
        # Open on caller thread to report permission/path errors immediately.
        file=sf.SoundFile(path,mode='w',samplerate=RATE,channels=2,subtype='PCM_16')
        self.record_queue=queue.Queue(maxsize=300)
        self.record_error=''
        self.recording=True
        def writer():
            try:
                with file:
                    while self.recording or not self.record_queue.empty():
                        try:
                            chunk=self.record_queue.get(timeout=.1)
                        except queue.Empty:
                            continue
                        file.write(chunk)
            except Exception as exc:
                self.record_error=str(exc)
                self.recording=False
        self.record_thread=threading.Thread(target=writer,daemon=True)
        self.record_thread.start()
    def stop_recording(self):
        self.recording=False
        if self.record_thread:
            self.record_thread.join(timeout=3)
            if self.record_thread.is_alive():
                raise RuntimeError('Le disque ne termine pas l’enregistrement.')
            self.record_thread=None
    def stop(self):
        self.running=False
        for stream in reversed(self.streams):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self.streams=[]
        self.outputs={}
        self.aux={}
        self.stop_recording()
    def diagnostics(self):
        streams=self.streams[:]
        return {'running':self.running,'error':self.error,
            'latencies_ms':[round(s.latency*1000,1) for s in streams],
            'cpu_percent':round(max((s.cpu_load for s in streams),default=0)*100,1),
            'events':self.status_events,
            'buffers':{k:{'underflows':b.underruns,'overflows':b.overruns} for k,b in self.outputs.items()}}
