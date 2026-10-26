SECURESENSE-24 standalone ESP-IDF project.
1) Copy main/ss24_wifi_config.example.h to main/ss24_wifi_config.h (this new file is ignored by Git).
2) Edit lab 2.4 GHz Wi-Fi credentials inside the copied file only.
3) From firmware/ in ESP-IDF 6.x: idf.py set-target esp32s3 && idf.py build
4) Flash the correct COM port and inspect event=radar, event=wifi, event=csi lines.
5) Close the monitor before launching windows_app.
Read ../docs/WIRING.md for safe VCC and GPIO17/GPIO18 connections.
