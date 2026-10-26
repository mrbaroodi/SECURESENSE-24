# Architecture and telemetry

## Data flow

```text
Local 2.4-GHz router  <~~~~ Wi-Fi CSI + ICMP replies ~~~~> ESP32-S3
                                                          |
HLK-LD2410B 24-GHz radar ---- UART1 256000 ----------------+
                                                          |
                                                USB serial 115200
                                                          |
                                                      Windows PC
                                                Python serial bridge
                                                          |
                                             http://127.0.0.1:8765
                                                          |
                           Monitor / DSP / Wireless-CSI / Cryptography
```

The **24 GHz radar** and **2.4 GHz CSI** are distinct sensing paths. The radar has its own onboard 24 GHz signal processing; the ESP32 receives processed energy and distance. Wi-Fi CSI comes from the ESP32 radio from local router packets. There is no direct 24 GHz RF capture.

## End-to-end telemetry

One JSON message per line with the prefix `SS24:`. Other ESP-IDF log lines are ignored by Python.

```text
SS24:{"event":"radar","seq":1,"state":1,"moving":true,"stationary":false,"display_distance_cm":120,"moving_energy":55,"stationary_energy":8}
SS24:{"event":"wifi","connected":true,"ip":"192.168.1.50","channel":11,"rssi":-48}
SS24:{"event":"csi","seq":1,"rssi":-48,"channel":11,"subcarrier_amplitude":[12,14,15,12,13]}
```

These are **format examples**, not captured experimental recordings. `state` in radar may be 0=no target, 1=moving, 2=stationary, 3=simultaneous moving/stationary detection channels **not** a count of two people.

### Firmware sequence

1. Read LD2410B 23-byte basic reporting frame over UART1 and validate header/tail.
2. Publish `radar` JSON frame.
3. Connect ESP32-S3 to local 2.4 GHz AP, register CSI callback and create an output queue; callback retains frames from associated AP.
4. With DHCP gateway, trigger local ICMP requests; capture IQ-derived amplitudes from response frames.
5. Limit CSI output to keep 115200 serial console responsive; send `csi` and periodic `wifi` JSON over USB.

### Windows sequence

1. Enumerate COM ports and attach to user-selected port using pyserial.
2. Parse `SS24:` JSON and maintain rolling radar and CSI history.
3. Build inter-frame CSI change feature, collect a quiet-room baseline over ~12 s, use robust median/MAD noise estimates and threshold hysteresis.
4. Expose local `/api/status` endpoint and CSV exports; serve static dashboard.
5. AES-GCM lab encrypts/decrypts user-selected **payloads** (it does not protect serial transport).

### Frequency-domain DSP interpretation

The current dashboard's FFT is computed from **time-varying telemetry**, not from raw radio-frequency IQ at carrier frequencies. `RSSI` is received power indication, not channel structure. The CSI amplitude array uses a fixed number of approximately selected IQ pairs; it is not a calibrated per-subcarrier OFDM channel response with precise index mapping.

### Evaluation caveats

A run of 20 s contains many correlated CSI frames. Sample-level TP/FP/TN/FN metrics help compare conditions, but do not establish sensitivity/specificity in the broader statistical population. Repeat sessions over rooms, people, distances and network conditions. Report failures and `INSUFFICIENT DATA` explicitly.
