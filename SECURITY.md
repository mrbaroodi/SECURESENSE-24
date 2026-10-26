# Security and Privacy — Private Deployment

- Keep the GitHub repository **Private**. Only authorize collaborators who need access, and review access periodically.
- Run the local web application on trusted Windows hosts. Its HTTP server binds to `127.0.0.1:8765`, not to the network interface.
- **USB serial is plaintext.** The AES-256-GCM function is an authenticated-encryption experiment; it does **not** encrypt live serial or CSI transport.
- Use a dedicated local Wi-Fi lab network with a strong WPA2-AES password; Internet access is unnecessary.
- `firmware/main/ss24_wifi_config.h` is intentionally ignored by Git. Only the placeholder `ss24_wifi_config.example.h` should be tracked.
- Network scans, CSV telemetry, participant observations, credentials and screenshots with personal or private information must be reviewed and sanitized before sharing with invited collaborators.
- This is a research prototype, not a certified medical, alarm, security or safety-critical system.

Report security issues privately to the repository owner. Do not create public disclosures or publish credentials.
