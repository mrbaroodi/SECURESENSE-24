# Troubleshooting

| Symptom | Check |
|---|---|
| `GPIO_NUM_17 undeclared` during build | Use current repo source, which sets `#define RADAR_TX 17` and `#define RADAR_RX 18`. |
| `ss24_wifi_config.h: No such file` | Copy `firmware/main/ss24_wifi_config.example.h` to `firmware/main/ss24_wifi_config.h`; edit private lab credentials. |
| `idf.py` not found | Open an activated ESP-IDF PowerShell/Command Prompt or ESP-IDF VS Code terminal, not a regular unconfigured shell. |
| Build fails about target | From `firmware/`: `idf.py set-target esp32s3` then `idf.py build` with ESP-IDF 6.x. |
| ESP32 shows boot logs but no `SS24:` lines | Wait for application; verify flashed correct board and no runtime crash. |
| `radar` missing, Wi-Fi working | Check radar regulated 5 V supply, common ground, RX↔TX crossover, GPIO17/18 and UART1 256000. |
| `wifi connected: false` | Check SSID/password in ignored header, 2.4 GHz network, WPA2 settings, DHCP enabled. |
| `wifi` appears but no `csi` | Confirm router advertises DHCP gateway, ICMP replies and capture settings; verify the Wi-Fi CSI component option and real router packet traffic. |
| No COM port in dashboard | Correct data USB cable, Windows device driver, ESP32 enumeration, not phone-charge-only cable. |
| COM is busy or permission denied | Close `idf.py monitor` with **Ctrl + ]** before Windows app CONNECT. Only one process may own the port. |
| App opens but motion classifier says `CALIBRATING` | Stay still for 12 s **while CSI frames arrive**; insufficient samples may require retry. |
| `INSUFFICIENT DATA` or no CSI frames | Improve 2.4 GHz router reception and packet activity, then hit RECALIBRATE while room is quiet. |
| CSI jitter with a still room | CSI changes with channel noise and interference, not solely movement; retest with fixed router position and repeat calm-room baseline. |
| Router survey blank | Windows needs a supported enabled WLAN adapter. Ethernet-only PC may still get ESP32 CSI through USB. |
| Port `8765` already in use | Close the older SECURESENSE-24 server instance before running the new one. |
| Cryptography lab rejects a token | Wrong password, corrupted ciphertext, or malformed token; AES-GCM authenticates payloads. |
| Dashboard does not have personal network names | The private GitHub package intentionally omits real credentials and measurement recordings. |

For fixes, preserve the original successful ESP-IDF firmware backup before reflashing. Do not assume a specific development board's 5 V/VIN pin produces an adequate voltage.
