# ESP32-S3 firmware: radar + offline Wi-Fi CSI

This is a **standalone ESP-IDF project** targeting `esp32s3`, extracted from the version tested on the original hardware. The code produces line-delimited `SS24:` JSON over the USB serial console and reads the LD2410B using UART1.

**Do not change firmware on a working device unless you want to reflash.** Authorized collaborators must configure a dedicated lab SSID/password before building.

1. Install and open an **ESP-IDF 6.x environment** (original development used ESP-IDF 6.1).
2. Copy `main/ss24_wifi_config.example.h` to `main/ss24_wifi_config.h`, then edit only the copied file.
3. From this `firmware/` directory run:

   ```powershell
   idf.py set-target esp32s3
   idf.py build
   idf.py -p COM5 flash monitor
   ```

   Replace COM5 with your actual port. `sdkconfig.defaults` enables `CONFIG_ESP_WIFI_CSI_ENABLED=y`.

4. Confirm `SS24:{"event":"radar"...}`, `SS24:{"event":"wifi"...}`, and `SS24:{"event":"csi"...}` lines in the monitor. `wifi` requires a router association. CSI requires frames from the AP (local ICMP requests are generated when the router advertises a gateway).
5. Close the ESP-IDF monitor (`Ctrl + ]`) before you open the Windows application, otherwise COM access will fail.

For pin wiring see [docs/WIRING.md](../docs/WIRING.md) and the diagram [docs/wiring.svg](../docs/wiring.svg). **Radar supply is not the same as 3.3 V UART logic.**

Implementation limitations:

- Number of stored CSI amplitudes: up to 52 indexed magnitudes from the available CSI IQ stream. The indices are **not mapped to calibrated physical subcarriers**; avoid treating them as a fully decoded channel-frequency response.
- CSI delivery is rate-limited to approximately 8 messages/second to keep serial output responsive.
- The firmware automatically pings the local router's gateway. Some routers may not provide a gateway or answer ICMP in offline configurations.
- Station mode is configured for WPA2-PSK or stronger compatible security; use a 2.4 GHz lab network.
- A working experiment does not establish accuracy across rooms, users, devices, firmware versions or RF conditions.
