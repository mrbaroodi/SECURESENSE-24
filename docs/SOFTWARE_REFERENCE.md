# Source-code walkthrough

This file is a reading map to the actual code — not a duplicate implementation.

## C / ESP-IDF

- `firmware/main/hello_world_main.c`
  - `radar_task()`: installs UART1 with RX/TX pins GPIO18/GPIO17 and 256000 baud, feeds bytes into a fixed-size packet parser.
  - `valid_frame()`: checks LD2410 basic-report signature, length, and tail before processing.
  - `emit_radar()`: converts target state, moving/stationary energy and centimeter fields into a JSON event.
  - `wifi_csi_cb()`: gets CSI receive info from Espressif API; copies abbreviated amplitude data to a FreeRTOS queue. Do not block the Wi-Fi task.
  - `csi_output_task()`: produces a separate `csi` JSON event for Windows. No image, identity, or accurate multipath angle is produced.
  - `start_gateway_ping()`: sends ICMP requests to the DHCP gateway to encourage local AP response frames, no Internet needed.
  - `wifi_events()`: associates with AP, reconnects and emits link status, including IP/channel/RSSI.
  - `wifi_csi_start()`: starts station mode and enables CSI capture.
- `firmware/main/ss24_wifi_config.example.h`: **sanitized configuration template**. Copy to the ignored `ss24_wifi_config.h` for local building.
- `firmware/CMakeLists.txt`: top-level ESP-IDF build project.

## Python Windows backend

- `windows_app/main.py`
  - `RadarBridge`: serial listener for `SS24:` lines, parsing, rolling buffers and state updates.
  - `API`: localhost HTTP server, connects COM port, Wi-Fi survey and CSV exports, starts calibration and trials.
- `windows_app/csi_motion.py`
  - `CSIMotionDetector`: inter-frame amplitude variation, 12 s quiet baseline, robust median/MAD threshold, temporal smoothing and hysteresis.
  - `MotionEvaluation`: user labels `EMPTY`, `STILL`, `MOVING`, sample-level confusion matrix and F1.
- `windows_app/lab_tools.py`: Windows `netsh` Wi-Fi scan; 250000-iteration PBKDF2-HMAC-SHA256, AES-256-GCM and CSV serialization.

## Front-end code

- `windows_app/static/index.html`: four main areas (`PRESENCE MONITOR`, `SIGNAL / DSP`, `WIRELESS / CSI`, `CRYPTOGRAPHY`).
- `windows_app/static/styles.css`: dark minimal dashboard styling.
- `windows_app/static/app.js`: `/api/status` polling, radar graphic, CSI subcarrier plots, time-domain radar/CSI graphs and experimental controls.

## MATLAB

- `matlab/analyze_csi.m`: reads exported `securesense24_csi.csv` with **time_monotonic_s** added in the distributed private package. Plots RSSI, mean amplitude, robust inter-frame motion feature and interpolated *temporal* FFT. MATLAB is not an application dependency.

## Accuracy and limitations

The original hardware demonstration showed live radar and CSI records. Algorithm software tests use synthetic signals; no independent deployment-wide accuracy has been established. Sampling and CSV timestamps reflect host processing/USB reception and are not synchronized radio hardware timestamps.
