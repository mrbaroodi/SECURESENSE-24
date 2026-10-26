"""SECURESENSE-24 offline localhost radar dashboard.
Only a local Windows serial port and 127.0.0.1 are used. No telemetry leaves the PC.
"""
from __future__ import annotations

import json
import re
import os
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from lab_tools import wifi_survey, seal_text, open_text, csv_from_history
from csi_motion import CSIMotionDetector, MotionEvaluation
import csv
import io
from urllib.parse import urlparse

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    raise SystemExit("pyserial missing. Install with: py -3 -m pip install pyserial") from exc

WEB_ROOT = Path(__file__).resolve().parent / "static"
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765
SERIAL_BAUD = 115200  # ESP32 console USB: *not* the LD2410 UART1's 256000 baud.

class RadarBridge:
    def __init__(self):
        self.lock = threading.RLock()
        self.port = None
        self.handle = None
        self.reader = None
        self.stop_flag = threading.Event()
        self.error = ""
        self.last = None
        self.last_at = 0.0
        self.sample_count = 0
        self.motion_epoch = 0
        self.events = deque(maxlen=80)
        self.history = deque(maxlen=320)
        self.csi_history = deque(maxlen=500)
        self.csi_samples = deque(maxlen=600)
        self.wifi_status = {"connected": False, "ip": None, "channel": None, "rssi": None}
        self.csi_last = None
        self.csi_last_at = 0.0
        self.csi_count = 0
        self.csi_seq = None
        self.motion_detector = CSIMotionDetector()
        self.evaluation = MotionEvaluation()
        self.radar_seq = None
        self.radar_seq_gaps = 0
        self._add_event("APP INITIALIZED", "system")

    def _add_event(self, message: str, typ: str):
        self.events.appendleft({"at": time.strftime("%H:%M:%S"), "message": message, "type": typ})

    def connect(self, port: str):
        valid = {p.device for p in serial.tools.list_ports.comports()}
        if port not in valid:
            raise ValueError(f"Port {port!r} is not available. Select a listed COM port.")
        self.disconnect()
        ser = serial.Serial(port=port, baudrate=SERIAL_BAUD, timeout=0.3,
                            rtscts=False, dsrdtr=False, write_timeout=1)
        # Avoid holding USB-UART reset lines where the serial adapter supports them.
        try:
            ser.dtr = False
            ser.rts = False
        except (OSError, ValueError):
            pass
        with self.lock:
            self.port = port
            self.handle = ser
            self.error = ""
            self.last = None
            self.last_at = 0.0
            self.sample_count = 0
            self.motion_epoch = 0
            self.history.clear()
            self.csi_history.clear()
            self.csi_samples.clear()
            self.wifi_status = {"connected": False, "ip": None, "channel": None, "rssi": None}
            self.csi_last = None
            self.csi_last_at = 0.0
            self.csi_count = 0
            self.csi_seq = None
            self.motion_detector = CSIMotionDetector()
            self.evaluation = MotionEvaluation()
            self.radar_seq = None
            self.radar_seq_gaps = 0
            self._add_event(f"SERIAL LINK OPEN / {port}", "link")
            self.stop_flag = threading.Event()
            self.reader = threading.Thread(target=self._read_loop,
                                           args=(ser, self.stop_flag), daemon=True)
            self.reader.start()

    def disconnect(self):
        with self.lock:
            ser, thread, flag = self.handle, self.reader, self.stop_flag
            was_connected = ser is not None
            self.handle = None
            self.reader = None
            self.port = None
            flag.set()
            if was_connected:
                self._add_event("SERIAL LINK CLOSED", "link")
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.7)

    def _read_loop(self, ser, flag):
        try:
            while not flag.is_set():
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "replace").strip()
                # Ignore boot logs and other ESP-IDF diagnostics.
                idx = line.find("SS24:")
                if idx < 0:
                    continue
                try:
                    msg = json.loads(line[idx + 5:])
                except (ValueError, TypeError):
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("event") == "wifi":
                    try:
                        wifi_now = {
                            "connected": msg.get("connected") is True,
                            "ip": str(msg.get("ip", ""))[:64] if msg.get("connected") else None,
                            "channel": int(msg.get("channel",0)) if msg.get("connected") else None,
                            "rssi": int(msg.get("rssi",0)) if msg.get("connected") else None,
                        }
                    except (ValueError, TypeError):
                        continue
                    with self.lock:
                        state_changed = wifi_now['connected'] != self.wifi_status['connected']
                        self.wifi_status = wifi_now
                        if state_changed:
                            self._add_event("ROUTER LINK ESTABLISHED" if wifi_now["connected"] else "ROUTER LINK LOST", "link")
                    continue
                if msg.get("event") == "csi":
                    try:
                        rssi = int(msg['rssi'])
                        channel = int(msg['channel'])
                        seq = int(msg['seq'])
                        amps = msg.get('subcarrier_amplitude', [])
                        if not isinstance(amps, list) or len(amps)>192 or not 1<=channel<=14:
                            continue
                        amps = [min(1000,max(0,float(n))) for n in amps]
                        if not amps:
                            continue
                    except (ValueError,TypeError,KeyError):
                        continue
                    with self.lock:
                        self.csi_count += 1
                        now = time.monotonic()
                        sample_motion = self.motion_detector.ingest(amps, channel, now)
                        if sample_motion is not None:
                            csi_info = self.motion_detector.snapshot(now)
                            radar_recent = self.last_at and now-self.last_at < 3.0
                            radar_moving = bool(self.last['moving']) if radar_recent and self.last else None
                            self.evaluation.ingest(csi_info['motion'], radar_moving, csi_info['score'],
                                                   csi_info['calibrated'], now)
                        self.csi_seq = seq
                        self.csi_last_at = now
                        self.csi_last = {'rssi':rssi,'channel':channel,'seq':seq,
                                         'subcarrier_amplitude':amps}
                        self.csi_history.append({'t':round(self.csi_last_at,3),
                                                 'rssi':rssi,'channel':channel,
                                                 'mean_amplitude':round(sum(amps)/len(amps),2) if amps else 0,
                                                 'seq':seq,
                                                 'motion_feature':sample_motion['feature'] if sample_motion else None,
                                                 'motion_score':sample_motion['score'] if sample_motion else None})
                        self.csi_samples.append({'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S'),
                                                'time_monotonic_s':round(now,6),
                                                'seq':seq,'rssi':rssi,'channel':channel,'amp':amps,
                                                 'motion_feature':sample_motion['feature'] if sample_motion else None,
                                                 'motion_score':sample_motion['score'] if sample_motion else None,
                                                 'motion_detected':sample_motion['motion'] if sample_motion else None})
                        if not self.wifi_status['connected']:
                            self.wifi_status.update({'connected': True, 'channel':channel,'rssi':rssi})
                    continue
                if msg.get("event") != "radar":
                    continue
                try:
                    state = int(msg["state"])
                    if state not in (0, 1, 2, 3):
                        continue
                    moving = bool(state & 1)
                    present = state != 0
                    fields = ["moving_energy", "stationary_energy", "moving_distance_cm",
                              "stationary_distance_cm", "detection_distance_cm", "display_distance_cm"]
                    values = {field: max(0, min(65535, int(msg.get(field, 0)))) for field in fields}
                except (ValueError, TypeError, KeyError):
                    continue
                now = time.monotonic()
                with self.lock:
                    old_state = int(self.last["state"]) if self.last else None
                    self.last = {"state": state, "presence": present,
                                 "moving": moving, "stationary": bool(state & 2),
                                 "seq": int(msg.get("seq", 0)), **values}
                    self.last_at = now
                    next_seq = int(msg.get('seq',0))
                    if self.radar_seq is not None and next_seq > self.radar_seq + 1:
                        self.radar_seq_gaps += next_seq - self.radar_seq - 1
                    self.radar_seq = next_seq
                    self.sample_count += 1
                    self.history.append({"t": round(now, 2),
                                         "moving": values["moving_energy"],
                                         "still": values["stationary_energy"]})
                    if old_state is None:
                        self._add_event("FIRST VALID RADAR FRAME", "link")
                    if (old_state is None or not (old_state & 1)) and moving:
                        self.motion_epoch += 1
                        self._add_event("MOTION DETECTED", "alert")
                    elif old_state is not None and old_state != 0 and not present:
                        self._add_event("PRESENCE CLEARED", "info")
                    elif old_state is not None and old_state != state:
                        self._add_event("PRESENCE STATE CHANGED", "info")
        except (serial.SerialException, OSError) as ex:
            if not flag.is_set():
                with self.lock:
                    self.error = f"Serial connection failed: {ex}"
                    self._add_event("SERIAL LINK ERROR", "alert")
        finally:
            with self.lock:
                if self.handle is ser:
                    self.handle = None
                    self.port = None
                    self.wifi_status['connected'] = False
            try:
                ser.close()
            except Exception:
                pass

    def snapshot(self):
        with self.lock:
            age = time.monotonic() - self.last_at if self.last_at else None
            online = self.handle is not None and age is not None and age < 3.0
            csi_online = self.handle is not None and self.csi_last_at > 0 and (time.monotonic()-self.csi_last_at < 5)
            recent_csi = [p for p in self.csi_history if time.monotonic()-p['t'] <= 5.0]
            classifier = self.motion_detector.snapshot()
            evaluation = self.evaluation.snapshot()
            radar_moving = bool(self.last['moving']) if online and self.last else None
            radar_presence = bool(self.last['presence']) if online and self.last else None
            csi_motion = classifier['motion'] if csi_online else None
            if radar_presence is True and (radar_moving or csi_motion is True):
                fusion_state = 'MOTION DETECTED'
            elif radar_presence is True:
                fusion_state = 'STATIONARY PRESENCE'
            elif radar_presence is False and csi_motion is True:
                fusion_state = 'CSI ACTIVITY / NO RADAR TARGET'
            elif radar_presence is False:
                fusion_state = 'NO TARGET'
            elif csi_motion is True:
                fusion_state = 'CSI ACTIVITY / RADAR OFFLINE'
            else:
                fusion_state = 'NO VALID TELEMETRY'
            agreement = ('AGREE' if radar_moving == csi_motion else 'DISAGREE') if radar_moving is not None and csi_motion is not None else 'NOT COMPARABLE'
            return {
                "classifier": classifier,
                "evaluation": evaluation,
                "fusion": {'state':fusion_state, 'agreement':agreement,'radar_motion':radar_moving,
                           'radar_presence':radar_presence,'csi_motion':csi_motion},
                "connected": self.handle is not None,
                "radar_online": online,
                "port": self.port, "error": self.error,
                "last_age_sec": round(age, 1) if age is not None else None,
                "last": self.last if online else None,
                "frames": self.sample_count,
                "motion_epoch": self.motion_epoch,
                "history": list(self.history)[-180:],
                "events": list(self.events)[:30],
                "mode": "LIVE USB / LOCALHOST ONLY",
                "radar_seq_gaps": self.radar_seq_gaps,
                "csi_online": csi_online,
                "wifi_status": self.wifi_status if self.handle is not None else {"connected": False},
                "csi_rate_hz": round(len(recent_csi)/5.0, 1),
                "csi_frames":self.csi_count,
                "csi_last":self.csi_last,
                "csi_history":list(self.csi_history)[-180:],
            }

RADAR = RadarBridge()

class API(BaseHTTPRequestHandler):
    server_version = "SecureSense24/1.4"
    def log_message(self, format, *args):
        # Silence high-frequency status polling logs.
        if not self.path.startswith("/api/status"):
            super().log_message(format, *args)

    def respond_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            return self.respond_json(RADAR.snapshot())
        if path == "/api/wifi/scan":
            return self.respond_json(wifi_survey())
        if path == "/api/export/evaluation.csv":
            with RADAR.lock:
                rows = list(RADAR.evaluation.rows)
            output=io.StringIO(newline='')
            w=csv.writer(output)
            w.writerow(['session','time_monotonic_sec','operator_label','csi_motion_detected','radar_moving','csi_score'])
            for r in rows:
                w.writerow([r['session'],r['t'],r['phase'],int(r['csi_motion']),
                            '' if r['radar_motion'] is None else int(r['radar_motion']),r['score']])
            data=output.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="securesense24_evaluation.csv"')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)
            return
        if path in ("/api/export/radar.csv", "/api/export/csi.csv"):

            kind = 'csi' if 'csi.csv' in path else 'radar'
            with RADAR.lock:
                history = list(RADAR.csi_samples if kind=='csi' else RADAR.history)
            if kind=='csi':
                io_buf = io.StringIO()
                width = max((len(s['amp']) for s in history), default=0)
                header = ['timestamp','time_monotonic_s','seq','rssi_dBm','wifi_channel','motion_feature','motion_score','motion_detected'] + [f'subcarrier_{i}_amplitude' for i in range(width)]
                writer=csv.writer(io_buf)
                writer.writerow(header)
                for sample in history:
                    writer.writerow([sample['timestamp'],sample.get('time_monotonic_s', ''),sample['seq'],sample['rssi'],sample['channel'],
                                     sample.get('motion_feature'),sample.get('motion_score'),sample.get('motion_detected'),*sample['amp']])
                csv_data = io_buf.getvalue().encode('utf-8-sig')
            else:
                csv_data = csv_from_history(history,kind).encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="securesense24_{kind}.csv"')
            self.send_header('Content-Length',str(len(csv_data)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(csv_data)
            return
        if path == "/api/ports":
            ports = [{"device": x.device, "description": x.description}
                     for x in serial.tools.list_ports.comports()]
            return self.respond_json({"ports": ports})
        paths = {"/": "index.html", "/index.html": "index.html",
                 "/styles.css": "styles.css", "/app.js": "app.js"}
        if path not in paths:
            return self.respond_json({"error": "Not found"}, 404)
        file = WEB_ROOT / paths[path]
        if not file.is_file():
            return self.respond_json({"error": "Asset not found"}, 404)
        mime = {".html": "text/html", ".css": "text/css", ".js": "application/javascript"}[file.suffix]
        body = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        # The server only listens on loopback. Reject non-JSON POSTs as a basic CSRF barrier.
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.respond_json({"error": "Expected JSON content type"}, 415)
        origin = self.headers.get("Origin", "")
        if origin and origin not in (f"http://{HTTP_HOST}:{HTTP_PORT}",):
            return self.respond_json({"error": "Origin not allowed"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 250_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/crypto/encrypt":
                if not isinstance(payload,dict): raise ValueError('Invalid JSON')
                return self.respond_json(seal_text(payload.get('plaintext',''), payload.get('password','')))
            if self.path == "/api/crypto/decrypt":
                if not isinstance(payload,dict): raise ValueError('Invalid JSON')
                return self.respond_json(open_text(payload.get('token',''), payload.get('password','')))
            if self.path == "/api/csi/calibrate":
                with RADAR.lock:
                    if RADAR.handle is None:
                        raise ValueError('Connect ESP32-S3 first')
                    RADAR.motion_detector.begin_calibration(manual=True)
                    RADAR._add_event('CSI CALIBRATION STARTED / KEEP ROOM STILL', 'info')
                return self.respond_json({'ok':True, 'message':'12-second CSI calibration started; remain still'})
            if self.path == "/api/evaluation/start":
                label=payload.get('label','')
                with RADAR.lock:
                    if not RADAR.motion_detector.snapshot()['calibrated']:
                        raise ValueError('Calibrate CSI first')
                    outcome=RADAR.evaluation.start(label)
                    RADAR._add_event('VALIDATION '+label+' / 20S', 'info')
                return self.respond_json({'ok':True,'evaluation':outcome})
            if self.path == "/api/evaluation/reset":
                with RADAR.lock:
                    RADAR.evaluation = MotionEvaluation()
                    RADAR._add_event('VALIDATION COUNTS CLEARED', 'info')
                return self.respond_json({'ok':True})
            if self.path == "/api/connect":
                port = payload.get("port", "")
                if not isinstance(port, str) or len(port) > 100:
                    raise ValueError("Invalid COM port")
                RADAR.connect(port)
                return self.respond_json({"ok": True})
            if self.path == "/api/disconnect":
                RADAR.disconnect()
                return self.respond_json({"ok": True})
            return self.respond_json({"error": "Not found"}, 404)
        except (ValueError, serial.SerialException, OSError, TypeError) as ex:
            return self.respond_json({"error": str(ex)}, 400)


def main():
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), API)
    url = f"http://{HTTP_HOST}:{HTTP_PORT}"
    print(f"\nSECURESENSE-24 / Windows local dashboard\nOpen: {url}\nPress Ctrl+C to stop.\n")
    threading.Thread(target=lambda: (time.sleep(0.7), webbrowser.open(url)), daemon=True).start()
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        RADAR.disconnect()
        httpd.server_close()

if __name__ == "__main__":
    main()
