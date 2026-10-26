"""Motion from *changes* in Wi-Fi CSI amplitude, not human counting or RF spectrum.

Algorithm: robust per-frame amplitude-difference feature; quiet-window median/MAD
calibration; independent rising/falling thresholds and debouncing. All motion scores
are heuristic, NOT probabilities or clinical measurements. No third-party DSP libs.
"""
from __future__ import annotations

import math
import statistics
import time
from collections import deque


def median(values):
    return statistics.median(values) if values else 0.0


class CSIMotionDetector:
    CAL_SECONDS = 12.0
    CAL_MIN_SAMPLES = 24

    def __init__(self):
        self.history = deque(maxlen=500)
        self.quiet_features = deque(maxlen=180)
        self.calibration_features = []
        self.noise_floor = None
        self.threshold = None
        self.calibration_start = None
        self.calibration_note = 'Warming up: keep room still during calibration'
        self.state = 'CALIBRATING'
        self.moving = False
        self.score = 0.0
        self.feature = 0.0
        self.ema = None
        self.prev = None
        self.prev_channel = None
        self.prev_time = None
        self.high_hits = 0
        self.low_hits = 0
        self.last_t = 0.0
        self.events = 0
        self.manual = False

    def begin_calibration(self, now=None, manual=False):
        now = time.monotonic() if now is None else now
        self.calibration_start = now
        self.calibration_features = []
        self.quiet_features.clear()
        self.noise_floor = None
        self.threshold = None
        self.state = 'CALIBRATING'
        self.moving = False
        self.score = 0.0
        self.ema = None
        self.prev = None
        self.prev_channel = None
        self.prev_time = None
        self.high_hits = 0
        self.low_hits = 0
        self.calibration_note = 'Keep the room empty/still until calibration completes'
        self.manual = manual

    def _finish_calibration(self):
        arr = self.calibration_features
        if len(arr) < self.CAL_MIN_SAMPLES:
            self.calibration_note = f'Not enough CSI samples ({len(arr)}/{self.CAL_MIN_SAMPLES}). Recalibrate when frames are steady.'
            self.state = 'INSUFFICIENT DATA'
            return False
        base = median(arr)
        mad = median([abs(v-base) for v in arr]) * 1.4826
        # Robust threshold: variability above the median, plus a minimum floor.
        self.noise_floor = max(0.002, base + 2.0 * mad)
        self.threshold = max(0.015, base + 6.0 * mad, 2.2 * self.noise_floor)
        self.state = 'STABLE'
        self.quiet_features.extend(arr)
        self.calibration_note = f'Calibrated on {len(arr)} CSI transitions; moving targets may require recalibration.'
        return True

    def ingest(self, amps, channel, now=None):
        now = time.monotonic() if now is None else now
        try:
            values = [float(x) for x in amps]
            if len(values) < 8 or len(values) > 192 or any(not math.isfinite(x) or x < 0 for x in values):
                return None
            channel = int(channel)
        except (ValueError, TypeError, OverflowError):
            return None

        if self.calibration_start is None:
            self.begin_calibration(now)
        if (self.prev is None or self.prev_channel != channel or len(self.prev) != len(values)
                or self.prev_time is None or now-self.prev_time > 2.0 or now <= self.prev_time):
            self.prev = values
            self.prev_channel = channel
            self.prev_time = now
            return None

        old = self.prev
        self.prev = values
        self.prev_time = now
        denom = max(1.0, median(old))
        diffs = [abs(a-b) for a,b in zip(values,old)]
        # Spatial median suppresses isolated noisy subcarriers and amplitude spikes.
        feature = median(diffs) / denom + 0.25 * abs(statistics.fmean(values)-statistics.fmean(old)) / denom
        feature = min(10.0,feature)
        self.feature = feature
        self.ema = feature if self.ema is None else 0.55*feature + 0.45*self.ema
        self.last_t = now

        if self.state == 'CALIBRATING':
            self.calibration_features.append(feature)
            if now-self.calibration_start >= self.CAL_SECONDS:
                self._finish_calibration()
        elif self.threshold is not None:
            # Debounced hysteresis: two positive samples to activate, four low samples to clear.
            if self.ema > self.threshold:
                self.high_hits += 1
                self.low_hits = 0
            elif self.ema < self.threshold*0.6:
                self.low_hits += 1
                self.high_hits = 0
            if not self.moving and self.high_hits >= 2:
                self.moving = True
                self.events += 1
            elif self.moving and self.low_hits >= 4:
                self.moving = False
            self.state = 'MOTION' if self.moving else 'STABLE'
            # Only update noise estimates in stable periods, at slow rate.
            if not self.moving and self.ema < self.threshold*0.55:
                self.quiet_features.append(feature)
                if len(self.quiet_features) >= 45 and len(self.history)%15 == 0:
                    arr = list(self.quiet_features)
                    base = median(arr)
                    mad = median([abs(v-base) for v in arr])*1.4826
                    candidate = max(0.015, base+6*mad,2.2*max(0.002,base+2*mad))
                    self.threshold = 0.98*self.threshold + 0.02*candidate

        if self.threshold is None:
            self.score = 0.0
        else:
            # Relative motion index, not a calibrated probability.
            self.score = min(100.0, max(0.0, 40.0*self.ema/max(self.threshold,1e-6)))
        row = {'t': round(now,3), 'feature':round(feature,5), 'smoothed':round(self.ema,5),
               'threshold':round(self.threshold,5) if self.threshold is not None else None,
               'score':round(self.score,1), 'motion': bool(self.moving),
               'calibrated':self.threshold is not None}
        self.history.append(row)
        return row

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        active = self.last_t > 0 and now-self.last_t <= 5.0
        if self.state == 'CALIBRATING' and self.calibration_start is not None:
            pct = min(100,round(100*(now-self.calibration_start)/self.CAL_SECONDS))
        else:
            pct = 100 if self.threshold is not None else 0
        return {'online':active,'calibrated':self.threshold is not None, 'state':self.state if active else 'CSI OFFLINE',
                'motion':bool(self.moving) if active and self.threshold is not None else None,
                'score':round(self.score,1) if active and self.threshold is not None else None,
                'feature':round(self.feature,5) if active else None,
                'threshold':round(self.threshold,5) if self.threshold is not None else None,
                'noise_floor':round(self.noise_floor,5) if self.noise_floor is not None else None,
                'calibration_percent':pct,'calibration_samples':len(self.calibration_features),
                'note':self.calibration_note,
                'events':self.events,'history':list(self.history)[-160:]}


class MotionEvaluation:
    """Operator labels are ground truth. Counts are correlated CSI frames, not independent trials."""
    def __init__(self):
        self.rows = []
        self.phase = None
        self.started = 0.0
        self.duration = 20.0
        self.session = 0

    def start(self, phase, now=None):
        if phase not in ('EMPTY','STILL','MOVING'):
            raise ValueError('Phase must be EMPTY, STILL or MOVING')
        now = time.monotonic() if now is None else now
        if self.phase is not None and now-self.started < self.duration:
            raise ValueError('A timed phase is already running')
        self.phase = phase
        self.started = now
        self.session += 1
        return self.snapshot(now)

    def ingest(self, csi_motion, radar_motion, csi_score, calibrated, now=None):
        now = time.monotonic() if now is None else now
        if self.phase is None:
            return
        if now-self.started >= self.duration:
            self.phase = None
            return
        if not calibrated or csi_motion is None:
            return
        self.rows.append({'session':self.session,'t':round(now,3),'phase':self.phase,
                          'csi_motion':bool(csi_motion), 'radar_motion':radar_motion,
                          'score':round(csi_score,2) if csi_score is not None else None})

    def snapshot(self, now=None):
        now=time.monotonic() if now is None else now
        if self.phase and now-self.started >= self.duration:
            self.phase = None
        tp=fp=tn=fn=0
        by_phase={label:0 for label in ('EMPTY','STILL','MOVING')}
        for r in self.rows:
            expected=r['phase']=='MOVING'
            detected=r['csi_motion']
            by_phase[r['phase']]+=1
            if expected and detected:tp+=1
            elif expected:fn+=1
            elif detected:fp+=1
            else:tn+=1
        def safe(num,den):return round(num/den*100,1) if den else None
        return {'phase':self.phase,'remaining_sec':round(max(0,self.duration-(now-self.started)),1) if self.phase else 0,
                'n':len(self.rows),'samples_per_phase':by_phase,
                'tp':tp,'fp':fp,'tn':tn,'fn':fn,
                'accuracy_pct':safe(tp+tn,tp+tn+fp+fn),
                'precision_pct':safe(tp,tp+fp), 'recall_pct':safe(tp,tp+fn),
                'specificity_pct':safe(tn,tn+fp), 'f1_pct':safe(2*tp,2*tp+fp+fn),
                'completed_phases':len(set(r['phase'] for r in self.rows)),
                'note':'Operator-labeled CSI frame metrics; samples within each 20s phase are correlated and are not independent trials.'}
