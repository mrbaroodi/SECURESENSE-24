"""Integration smoke test for actual-format SS24 wifi + CSI telemetry."""
import importlib.util
import json
from pathlib import Path
import queue
import sys
import time
import types
import unittest

root = Path(__file__).resolve().parents[1] / "windows_app"
sys.path.insert(0, str(root))
feed = queue.Queue()
fake_serial = types.ModuleType("serial")
fake_serial.SerialException = type("SerialException", (Exception,), {})

class FakeSerial:
    def __init__(self, **kwargs): self.dtr=False; self.rts=False
    def readline(self):
        try: return feed.get(timeout=.1)
        except queue.Empty: return b''
    def close(self): pass

fake_serial.Serial=FakeSerial
ports=types.ModuleType("serial.tools.list_ports")
ports.comports=lambda: [types.SimpleNamespace(device='COM95',description='Integration fake device')]
tools=types.ModuleType('serial.tools')
tools.list_ports=ports
fake_serial.tools=tools
sys.modules['serial']=fake_serial
sys.modules['serial.tools']=tools
sys.modules['serial.tools.list_ports']=ports

spec=importlib.util.spec_from_file_location('ss24_csi_test',root/'main.py')
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class CsiTest(unittest.TestCase):
    def test_wifi_and_csi_frames(self):
        b=app.RadarBridge();b.connect('COM95')
        for message in [
            {'event':'wifi','connected':True,'ip':'192.168.24.20','rssi':-49,'channel':6},
            {'event':'radar','seq':100,'state':1,'moving_energy':70,'display_distance_cm':131},
            {'event':'csi','seq':1,'channel':6,'rssi':-47,'subcarrier_amplitude':[12,31,25,20,14]},
            {'event':'csi','seq':2,'channel':6,'rssi':-47,'subcarrier_amplitude':[13,29,26,19,16]},
        ]: feed.put(('SS24:'+json.dumps(message)+'\r\n').encode())
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if b.snapshot()['csi_frames']>=2: break
            time.sleep(.02)
        snap=b.snapshot()
        self.assertEqual(snap['csi_frames'],2)
        self.assertTrue(snap['csi_online'])
        self.assertEqual(snap['wifi_status']['ip'],'192.168.24.20')
        self.assertEqual(snap['frames'],1)
        self.assertEqual(snap['csi_last']['subcarrier_amplitude'],[13.,29.,26.,19.,16.])
        self.assertEqual(len(b.csi_samples),2)
        self.assertEqual(b.csi_samples[-1]['amp'],[13.,29.,26.,19.,16.])
        b.disconnect()
        self.assertFalse(b.snapshot()['csi_online'])

if __name__=='__main__':unittest.main()
