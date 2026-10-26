import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'windows_app'))
from csi_motion import CSIMotionDetector, MotionEvaluation


class MotionClassificationTest(unittest.TestCase):
    def make_base(self, idx):
        return [70.0+7*math.sin(k*.3) + .25*math.sin(idx*.7+k*.2) for k in range(64)]

    def calibrated(self):
        det=CSIMotionDetector()
        for i in range(95):
            det.ingest(self.make_base(i),11,i*.2)
        self.assertTrue(det.snapshot(now=19)['calibrated'])
        self.assertFalse(det.moving)
        return det

    def test_movement_and_still(self):
        det=self.calibrated()
        self.assertLess(det.score,100)
        for i in range(95,110):
            j=i-95
            moving=[v + 22 * math.sin((j+1)*1.2+k*.08) for k,v in enumerate(self.make_base(i))]
            det.ingest(moving,11,i*.2)
        self.assertTrue(det.moving, 'CSI perturbation should exceed calibrated quiet baseline')
        self.assertGreater(det.score,40)
        for i in range(110,150):
            det.ingest(self.make_base(i),11,i*.2)
        self.assertFalse(det.moving,'Quiet CSI should clear motion state with hysteresis')

    def test_recalibrate(self):
        det=self.calibrated()
        det.begin_calibration(50.0, manual=True)
        self.assertIsNone(det.threshold)
        self.assertEqual(det.state,'CALIBRATING')
        for i in range(100):
            det.ingest(self.make_base(i),11,50+i*.2)
        self.assertTrue(det.snapshot(now=70)['calibrated'])
        self.assertTrue(det.manual)

    def test_channel_change_not_false_motion(self):
        det=self.calibrated()
        self.assertIsNone(det.ingest([999.0]*64,1,20))
        self.assertFalse(det.moving)
        self.assertIsNone(det.ingest([999.0]*32,1,21))

    def test_evaluation_metrics(self):
        val=MotionEvaluation()
        val.start('EMPTY',0)
        for i in range(5):val.ingest(False,False,9,True,i)
        val.start('MOVING',30)
        for i in range(4):val.ingest(i!=3,True,90,True,31+i)
        r=val.snapshot(60)
        self.assertEqual((r['tp'],r['fp'],r['tn'],r['fn']),(3,0,5,1))
        self.assertEqual(r['recall_pct'],75.0)
        self.assertAlmostEqual(r['accuracy_pct'],88.9)

if __name__=='__main__':unittest.main()
