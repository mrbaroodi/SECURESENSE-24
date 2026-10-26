# SECURESENSE-24 — Integrated Wireless Human-Presence and Signal-Analysis Laboratory

**Student:** Mohammed Younis Majid  
**Institution:** Northern Technical University — Cybersecurity & Cloud Computing Engineering  
**Disciplines:** Digital Signal Processing; Wireless Networks; Cryptography  
**Release:** Windows Laboratory v1.4

## Abstract

SECURESENSE-24 combines a single ESP32-S3 with a 24 GHz HLK-LD2410B presence radar and an isolated 2.4 GHz Wi-Fi router. The ESP32-S3 acquires UART radar frames and Wi-Fi Channel State Information (CSI), then transmits machine-readable telemetry over USB to a localhost Windows dashboard. The software visualizes motion and stationary-presence classifications, channel amplitudes, temporal spectra, packet statistics, and the results of an authenticated-encryption laboratory. Version 1.4 additionally implements a calibrated CSI change detector and operator-labeled experiments for comparing CSI motion decisions with radar observations. Human counting is outside the hardware's capability.

## Architecture

`LD2410B (24 GHz) --UART1 256000 baud--> ESP32-S3 <--2.4 GHz Wi-Fi CSI-- TP-Link TL-WR940N`

`ESP32-S3 --USB console 115200 baud / SS24 JSON--> Windows Python backend --> Browser on 127.0.0.1:8765`

The router operates on an isolated local Wi-Fi network without an Internet uplink. Its ICMP echo replies provide Wi-Fi frames received by the ESP32-S3 for CSI sampling. Network configurations and encryption keys are not embedded in this report.

## 1. Digital Signal Processing

### Radar measurements

The LD2410B supplies processed movement and stationary target energies, distance estimates and state classifications. These are **not raw 24 GHz IQ samples**. The Windows application displays the time series, a five-sample moving-average filter and a temporal-frequency FFT after resampling to an approximately uniform time grid.

### CSI feature and adaptive calibration

For each valid pair of consecutive CSI amplitude vectors `a_t[i]` and `a_(t-1)[i]` from the same Wi-Fi channel and coefficient count, the classifier calculates a dimensionless feature:

`D_t = median_i |a_t[i] - a_(t-1)[i]| / max(1, median_i a_(t-1)[i]) + 0.25 * |mean(a_t) - mean(a_(t-1))| / max(1, median_i a_(t-1)[i])`

A first-order exponential smoother is applied:

`S_t = 0.55 D_t + 0.45 S_(t-1)`

During an initial approximately 12-second stationary calibration window, baseline median `m` and robust deviation `MAD = 1.4826 × median(|D_t - m|)` are estimated. The motion-on threshold is the maximum of a fixed numerical floor, `m + 6 MAD`, and a relative noise term. A lower off threshold and multiple-frame debounce reduce chatter. Quiet-sample statistics subsequently adapt slowly. The normalized **motion index** maps relative change to 0–100 for presentation; it is a heuristic signal index, **not** a posterior probability of human activity.

Time-series FFT charts show **temporal frequencies of channel variation**, not raw RF spectra. Changes can originate from human motion, multipath, mechanical motion, nearby transmitters or firmware sampling variability.

## 2. Wireless Networks

The 2.4 GHz router acts as an access point, with no Internet connectivity required. The ESP32-S3 extracts CSI estimates from frames received over this local link. Wi-Fi diagnostics include channel, received RSSI, CSI frame count, CSI reporting rate and per-subcarrier amplitude. The Windows WLAN BSSID scan is a channel occupancy illustration and **not** a calibrated spectrum analyzer. Lost USB sequence numbers are not equal to lost wireless packets.

## 3. Cryptography

An AES-256-GCM laboratory demonstrates authenticated encryption, random 96-bit nonces, 128-bit tags, password-derived 256-bit keys using PBKDF2-HMAC-SHA256 and failure on wrong keys or modified ciphertext. The latest live radar/CSI snapshot may be loaded into the lab as plaintext. This demonstrates cryptographic confidentiality and integrity **for laboratory payloads only**; the current USB serial stream is not encrypted end-to-end. Wi-Fi access-point protection is provided separately by the configured WPA2 link.

## 4. CSI and Radar Fusion

The radar is the primary provider of human presence and approximate distance. CSI provides a separate motion/variation indicator. Fusion preserves sensor provenance: radar motion gives a moving detection; stationary radar presence combined with CSI motion is reported as motion with disagreement; CSI activity without radar presence is explicitly flagged as **unconfirmed activity** rather than an identified person. The marker position in the semicircular display is symbolic (there is no azimuth measurement).

## 5. Experimental Protocol and Metrics

After the 12-second quiet calibration, record three operator-labeled 20-second phases at the same sensor geometry:

| Phase | Physical procedure | Binary motion reference |
|---|---|---|
| EMPTY | Clear target area; avoid walking nearby | Negative |
| STILL | Sit or stand without walking | Negative |
| MOVING | Walk through the router–ESP32-S3 propagation path | Positive |

For each CSI sample, the application records a prediction and the operator's phase label. Confusion-matrix counts are **TP, FP, TN, FN**. Report metrics as:

`Accuracy = (TP + TN) / (TP + FP + TN + FN)`

`Precision = TP / (TP + FP)`

`Recall = TP / (TP + FN)`

`Specificity = TN / (TN + FP)`

`F1 = 2TP / (2TP + FP + FN)`

Metrics with zero denominators are shown as unavailable. Report the sample counts **and number of independent trials**. Since sequential CSI frames are correlated, sample-level percentages may overstate generalization. Repeating trials with changed distances, participant positions and room setups is necessary for a general accuracy claim.

### Results to be filled from the real application

| Measurement | Recorded result |
|---|---|
| CSI frames observed | *Complete after experiment* |
| Baseline noise floor | *Complete after calibration* |
| Adaptive threshold | *Complete after calibration* |
| Empty/still/moving labeled samples | *Complete after three phases* |
| TP / FP / TN / FN | *Complete from validation CSV* |
| Accuracy / Precision / Recall / Specificity / F1 | *Complete from validation results* |
| Cross-sensor agreement | *Evaluate from live comparisons* |

**No participant detection accuracy or false-positive rate is claimed before measurement.**

## Limitations and Safety

No people counting, target identity tracking, biometric identification, RF-band spectrum analysis or guaranteed human-only activity classification is provided. The prototype is an educational sensing laboratory. Radar and Wi-Fi electrical connections should follow the device supply and logic-level specifications; the successfully tested wiring need not be modified for this Windows release. No data needs to be uploaded to a cloud service.

## Implementation Verification

Version 1.4 software passed 10 automated Python tests and an offline browser smoke test for the principal user-interface pages. The firmware integrated with router CSI was verified separately by the user's earlier hardware testing, but this exact v1.4 classifier release has **not** been field validated on the user's Windows machine; its operator-labeled experiment should be run before final presentation.
