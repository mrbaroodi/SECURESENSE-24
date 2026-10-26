# MATLAB analysis of SECURESENSE-24 CSV

MATLAB is **optional** and **not used inside the running Windows dashboard**. The `analyze_csi.m` script processes actual CSV measurements exported by the dashboard.

1. In `WIRELESS / CSI` select **EXPORT CSI CSV** and save `securesense24_csi.csv` locally.
2. Change the filename in `analyze_csi.m` or place a CSV next to the script.
3. Run `analyze_csi` in MATLAB; it plots RSSI, mean CSI magnitude, normalized inter-frame variation, and an FFT of the uniformly resampled **temporal variation**.
4. The code requires actual measured data. It does not create or claim synthetic experimental results.

If you have older exports with only second-resolution timestamp strings, the FFT section will be skipped: you need `time_monotonic_s` column added to the GitHub-ready Windows app. This host-side timestamp is approximate USB receive time, not hardware-synchronized packet capture time.
