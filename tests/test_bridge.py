"""Local smoke test with fake serial port; no ESP32 needed."""
import importlib.util
import json
import pathlib
import queue
import sys
import time
import types
import unittest

app_path = pathlib.Path(__file__).resolve().parents[1] / "windows_app/main.py"
sys.path.insert(0,str(app_path.parent))
fake_serial = types.ModuleType("serial")
fake_serial.SerialException = type("SerialException", (Exception,), {})
feed = queue.Queue()

class FakeDevice:
    def __init__(self, **kwargs):
        self.port=kwargs['port']
        self.closed=False
        self.dtr=False
        self.rts=False
    def readline(self):
        try: return feed.get(timeout=0.15)
        except queue.Empty: return b''
    def close(self): self.closed=True

fake_serial.Serial = FakeDevice
list_ports = types.ModuleType("serial.tools.list_ports")
list_ports.comports=lambda: [types.SimpleNamespace(device="COM55",description="Test USB")]
serial_tools = types.ModuleType("serial.tools")
serial_tools.list_ports=list_ports
fake_serial.tools=serial_tools
sys.modules["serial"] = fake_serial
sys.modules["serial.tools"] = serial_tools
sys.modules["serial.tools.list_ports"] = list_ports
spec=importlib.util.spec_from_file_location("ss24",app_path)
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class BridgeTest(unittest.TestCase):
    def test_ingest_and_states(self):
        b=app.RadarBridge()
        b.connect("COM55")
        moving={"event":"radar","state":3,"seq":1,"moving_energy":69,"stationary_energy":21,"display_distance_cm":117}
        feed.put(b'ESP LOG\r\n')
        feed.put(('SS24:'+json.dumps(moving)+'\r\n').encode())
        limit=time.monotonic()+1.2
        while b.snapshot()['frames']<1 and time.monotonic()<limit: time.sleep(.02)
        st=b.snapshot()
        self.assertTrue(st['radar_online'])
        self.assertTrue(st['last']['moving'])
        self.assertEqual(st['last']['display_distance_cm'],117)
        self.assertEqual(st['motion_epoch'],1)
        feed.put(('SS24:'+json.dumps({**moving,"seq":2,"state":2})+'\r\n').encode())
        limit=time.monotonic()+1.2
        while b.snapshot()['frames']<2 and time.monotonic()<limit: time.sleep(.02)
        self.assertFalse(b.snapshot()['last']['moving'])
        feed.put(('SS24:'+json.dumps({**moving,"seq":3,"state":1})+'\r\n').encode())
        limit=time.monotonic()+1.2
        while b.snapshot()['frames']<3 and time.monotonic()<limit: time.sleep(.02)
        self.assertEqual(b.snapshot()['motion_epoch'],2)
        b.disconnect()
        self.assertFalse(b.snapshot()['connected'])

if __name__ == '__main__': unittest.main()
