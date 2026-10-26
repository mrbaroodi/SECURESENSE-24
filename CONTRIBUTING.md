# Internal Collaboration Policy

This repository is private and proprietary. Changes are accepted only from collaborators explicitly authorized by the owner, Mohammed Younis Majid. Access to the repository does not grant redistribution rights.

## Engineering checklist

- Keep hardware wiring, radar UART pin mapping, and power safety documentation consistent with firmware changes.
- Remove Wi-Fi passwords, SSIDs/BSSIDs, local network identifiers and real participant data from commits and logs.
- Run `python -m unittest discover -s tests -v` and `node --check windows_app/static/app.js` after code changes.
- Distinguish 24 GHz radar reporting from 2.4 GHz Wi-Fi CSI; do not mislabel temporal FFT as an RF spectrum.
- Do not claim human counting or general-purpose human identification using the existing sensors.
- Ask the repository owner before sharing patches, screenshots, project artifacts or reports beyond the approved collaborator group.
