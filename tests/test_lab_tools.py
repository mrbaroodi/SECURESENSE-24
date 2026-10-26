"""Simple local tests for SECURESENSE-24 laboratory modules."""
import base64
import json
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'windows_app'))
from lab_tools import seal_text,open_text,csv_from_history,wifi_survey

class LabToolsTest(unittest.TestCase):
    def test_roundtrip(self):
        data='{"state":1,"distance_cm":120}'
        token=seal_text(data,'correct-horse-battery')
        self.assertEqual(open_text(token['token'],'correct-horse-battery')['plaintext'],data)
        with self.assertRaises(ValueError): open_text(token['token'],'wrong-password')

    def test_tampered_token_fails(self):
        token=seal_text('sensitive demo','classroom-passphrase')['token']
        env=json.loads(base64.urlsafe_b64decode(token))
        ct=env['ciphertext']
        env['ciphertext']=('A' if ct[0]!='A' else 'B')+ct[1:]
        corrupt=base64.urlsafe_b64encode(json.dumps(env).encode()).decode()
        with self.assertRaises(ValueError): open_text(corrupt,'classroom-passphrase')

    def test_radar_csv(self):
        csv=csv_from_history([{'t':12.0,'moving':50,'still':30}],'radar')
        self.assertIn('motion_energy_0_100',csv)
        self.assertIn('12.0,50,30',csv)

    def test_wifi_graceful_on_nonwindows(self):
        self.assertIn('available',wifi_survey())

if __name__=='__main__':unittest.main()
