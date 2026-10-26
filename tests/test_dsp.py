import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dsp import Processor,Settings,RNNoise,validated_settings,amp,dbfs
from engine import AudioEngine,ElasticBuffer,Strip

class AudioTests(unittest.TestCase):
    def tone(self,amplitude=.2):return amplitude*np.sin(2*np.pi*1000*np.arange(480)/48000)
    def test_silence_and_mute(self):
        p=Processor()
        for _ in range(50):self.assertTrue(np.all(p.process(np.zeros(480),Settings(ai=False))==0))
        self.assertTrue(np.all(p.process(self.tone(),Settings(mute=True))==0))
    def test_peak_limiter(self):
        p=Processor();y=p.process(self.tone(10),Settings(gain=24,ceiling=-3,ai=False))
        self.assertLessEqual(np.max(np.abs(y)),amp(-3)+1e-6)
        self.assertTrue(p.clipping)
    def test_compression(self):
        p=Processor();s=Settings(ai=False,highpass=False,gate=-90,threshold=-30,ratio=8,makeup=0,deesser=0)
        for _ in range(100):y=p.process(self.tone(.5),s)
        self.assertLess(np.sqrt(np.mean(y*y)),.08)
    def test_gate_and_hold(self):
        p=Processor();s=Settings(ai=False,highpass=False,gate=-40,threshold=0,ratio=1,makeup=0,deesser=0)
        for _ in range(100):p.process(self.tone(),s)
        self.assertGreater(p.gate_gain,.99)
        for _ in range(5):p.process(self.tone(.0001),s)
        self.assertGreater(p.gate_gain,.99)
        for _ in range(250):y=p.process(self.tone(.0001),s)
        self.assertLess(np.max(np.abs(y)),1e-7)
    def test_eq(self):
        x=.05*np.sin(2*np.pi*1250*np.arange(480)/48000)
        p=Processor();s=Settings(ai=False,highpass=False,gate=-90,ratio=1,makeup=0,deesser=0,eq=(0,0,0,0,6,0,0,0))
        for _ in range(50):y=p.process(x,s)
        self.assertGreater(dbfs(y)-dbfs(x),4)
    def test_profile_validation(self):
        for bad in [{'gain':float('nan')},{'eq':[0]*7},{'gain':999},{'ai':'yes'},{'unknown':2}]:
            with self.assertRaises(ValueError):validated_settings(bad)
        self.assertEqual(validated_settings({'eq':[0]*8}).eq,(0,)*8)
    def test_buffer_bounded_and_clock_drift(self):
        b=ElasticBuffer(max_blocks=4)
        for _ in range(100):b.put(np.ones(480,dtype=np.float32))
        self.assertLessEqual(b.queue.qsize(),4)
        self.assertGreater(b.overruns,0)
        y=b.read(480);self.assertEqual(y.shape,(480,));self.assertTrue(np.isfinite(y).all())
        for _ in range(10):b.read(480)
        self.assertGreater(b.underruns,0)
    def test_routes_mute_and_solo(self):
        e=AudioEngine();e.settings=Settings(ai=False,bypass=True);e.monitor_enabled=True
        e.strips=(Strip(monitor=True,broadcast=False),Strip(),Strip(),Strip())
        e.outputs={'monitor':ElasticBuffer(),'broadcast':ElasticBuffer()}
        e._mix(self.tone()[:,None],480,None,None)
        self.assertGreater(e.bus_levels[0],-80);self.assertEqual(e.bus_levels[1],-180)
        e.strips=(Strip(solo=False),Strip(solo=True),Strip(),Strip())
        e._mix(self.tone()[:,None],480,None,None)
        self.assertEqual(e.bus_levels[0],-180)
    def test_stream_failure_closes_opened_stream(self):
        e=AudioEngine()
        from unittest.mock import Mock
        first=Mock()
        with patch('engine.sd.query_devices',return_value={'max_output_channels':2}),patch('engine.wasapi_settings',return_value=None),patch('engine.sd.OutputStream',return_value=first),patch('engine.sd.InputStream',side_effect=RuntimeError('no mic')):
            with self.assertRaises(RuntimeError):e.start(0,monitor=1)
        first.close.assert_called_once();self.assertFalse(e.running);self.assertEqual(e.streams,[])
    def test_recording_flush(self):
        import soundfile as sf
        e=AudioEngine();e.running=True
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.wav';e.start_recording(path)
            for _ in range(10):e.record_queue.put(np.ones((480,2),dtype=np.float32)*.1)
            e.stop_recording();data,rate=sf.read(path)
            self.assertEqual(rate,48000);self.assertEqual(data.shape,(4800,2))
    def test_native_ai(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'native'/('rnnoise.dll' if sys.platform=='win32' else 'librnnoise.so')
        if not path.exists():
            if os.environ.get('MICSTUDIO_REQUIRE_AI'):self.fail('RNNoise DLL missing')
            self.skipTest('Native module unavailable in this environment')
        ai=RNNoise(path)
        try:
            rng=np.random.default_rng(42)
            outputs=[];inputs=[]
            for _ in range(250):
                x=rng.normal(0,.015,480).astype(np.float32);outputs.append(ai.process(x));inputs.append(x)
            self.assertTrue(np.isfinite(outputs).all())
            self.assertLess(dbfs(np.concatenate(outputs[-100:])),dbfs(np.concatenate(inputs[-100:]))-3)
            self.assertTrue(0<=ai.probability<=1)
            ai.reset()
        finally:ai.close()

if __name__=='__main__':unittest.main()
