import unittest
import numpy as np
from dsp import Processor, Settings

class AudioTests(unittest.TestCase):
    def test_silence(self):
        p = Processor()
        for _ in range(100):
            y = p.process(np.zeros(480), Settings())
            self.assertTrue(np.isfinite(y).all())
            self.assertEqual(float(np.max(np.abs(y))), 0)
    def test_mute_and_safety(self):
        p = Processor()
        x = np.full(480, 100, dtype=np.float32)
        self.assertTrue(np.all(p.process(x, Settings(mute=True)) == 0))
        self.assertLessEqual(float(np.max(np.abs(p.process(x, Settings(gain=24))))), .980001)
    def test_gate_closes_and_opens(self):
        p = Processor()
        s = Settings(highpass=False, gate=-40, threshold=0)
        t = np.arange(480)/48000
        for _ in range(150):
            y = p.process(.1*np.sin(2*np.pi*1000*t), s)
        self.assertGreater(np.max(np.abs(y)), .09)
        for _ in range(200):
            y = p.process(.0001*np.sin(2*np.pi*1000*t), s)
        self.assertLess(np.max(np.abs(y)), 1e-7)
    def test_bypass(self):
        x = np.linspace(-.5,.5,480,dtype=np.float32)
        np.testing.assert_array_equal(Processor().process(x,Settings(bypass=True)),x)
    def test_compression(self):
        p = Processor()
        x = .5*np.sin(2*np.pi*1000*np.arange(480)/48000)
        for _ in range(100):
            y = p.process(x,Settings(highpass=False,gate=-80,threshold=-30,ratio=8))
        self.assertLess(np.sqrt(np.mean(y*y)), .08)

if __name__ == '__main__':
    unittest.main()
