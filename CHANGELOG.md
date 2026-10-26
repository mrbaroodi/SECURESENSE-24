# Changelog

## v1.4 GitHub-ready packaging (October 2026)
- Private proprietary repository tree, standalone ESP-IDF project, wiring schematic, English-only instructions, internal notices, CI and MATLAB analysis script.
- Replaced tracked Wi-Fi configuration with an ignored local configuration template.
- Preserved verified GPIO17/GPIO18 UART setup using numeric GPIO arguments.
- Added host-monotonic timestamps to exported CSI CSV for reproducible time-domain analysis.

## v1.4 application
- Adaptive CSI motion threshold, radar/CSI comparison, evaluation recording, and offline AES-256-GCM lab.

## v1.3 firmware
- ESP32-S3 receives LD2410B UART radar data and local 2.4GHz Wi-Fi CSI from the AP, transmits `SS24:` JSON frames to Windows.
