"""Offline experiments for SECURESENSE-24: Wi-Fi survey and authenticated encryption.

Neither a Wi-Fi channel survey nor radar energy is a true RF spectrum.
The USB serial link is not encrypted; AES-GCM here protects *lab payloads*.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import locale
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

AAD = b"SECURESENSE24-AESGCM-LAB-v1"
ITERATIONS = 250_000


def derive_key(password: str, salt: bytes) -> bytes:
    if not 8 <= len(password) <= 512:
        raise ValueError("Passphrase must be 8 to 512 characters")
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS).derive(password.encode("utf-8"))


def seal_text(plaintext: str, password: str) -> dict:
    if len(plaintext.encode("utf-8")) > 100_000:
        raise ValueError("Maximum plaintext is 100 KB")
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    cipher = AESGCM(derive_key(password, salt)).encrypt(nonce, plaintext.encode('utf-8'), AAD)
    envelope = {"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-HMAC-SHA256",
                "iterations": ITERATIONS,
                "salt": base64.b64encode(salt).decode(),
                "nonce": base64.b64encode(nonce).decode(),
                "ciphertext": base64.b64encode(cipher).decode()}
    token = base64.urlsafe_b64encode(json.dumps(envelope, separators=(',', ':')).encode()).decode()
    return {"token": token, "algorithm": "AES-256-GCM", "bytes": len(cipher), "authenticated": True}


def open_text(token: str, password: str) -> dict:
    try:
        if len(token) > 250_000:
            raise ValueError('Token too long')
        envelope = json.loads(base64.urlsafe_b64decode(token.encode('ascii')))
        if envelope.get('v') != 1 or envelope.get('alg') != 'AES-256-GCM' or envelope.get('iterations') != ITERATIONS:
            raise ValueError('Unsupported envelope parameters')
        salt = base64.b64decode(envelope['salt'], validate=True)
        nonce = base64.b64decode(envelope['nonce'], validate=True)
        ciphertext = base64.b64decode(envelope['ciphertext'], validate=True)
        if len(salt) != 16 or len(nonce) != 12 or len(ciphertext) < 16:
            raise ValueError('Invalid salt, nonce or ciphertext')
        clear = AESGCM(derive_key(password, salt)).decrypt(nonce, ciphertext, AAD)
        return {"plaintext": clear.decode('utf-8'), "verified": True}
    except (UnicodeError, ValueError, KeyError, TypeError, InvalidTag, json.JSONDecodeError, base64.binascii.Error) as e:
        raise ValueError('Authentication failed: wrong password or modified/invalid ciphertext') from e


def csv_from_history(history: list[dict], kind: str) -> str:
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    if kind == 'csi':
        writer.writerow(['time_monotonic_s', 'rssi_dbm', 'channel', 'mean_amplitude', 'csi_frame_seq'])
        for item in history:
            writer.writerow([item.get(x,'') for x in ('t', 'rssi', 'channel', 'mean_amplitude', 'seq')])
    else:
        writer.writerow(['time_monotonic_s', 'motion_energy_0_100', 'still_energy_0_100'])
        for item in history:
            writer.writerow([item.get('t',''),item.get('moving',''),item.get('still','')])
    return output.getvalue()


def wifi_survey() -> dict:
    """Reads Windows Wi-Fi adapter scan, not RF waveform or CSI.
    Requires an enabled WLAN adapter; Ethernet alone is insufficient for scan.
    """
    if sys.platform != 'win32':
        return {"available": False, "reason": 'Wi-Fi survey requires Windows netsh and an enabled Wi-Fi adapter', "networks": []}
    try:
        proc = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], capture_output=True,
                              timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"available": False, "reason": str(e), "networks": []}
    raw = proc.stdout + b'\n' + proc.stderr
    decoded = []
    for encoding in ['utf-8-sig', 'mbcs', locale.getpreferredencoding(False), 'cp866', 'cp1256']:
        try:
            candidate = raw.decode(encoding, errors='replace')
            if candidate not in decoded: decoded.append(candidate)
        except LookupError:
            continue
    text = max(decoded, key=lambda v: (v.count('SSID'), v.count('BSSID'), v.count('Channel'), v.count('\u0627\u0644\u0642\u0646\u0627\u0629')))
    networks, ssid, current = [], '', None
    def flush():
        nonlocal current
        if current and current.get('channel') and current.get('signal_percent') is not None:
            networks.append(current)
        current = None
    for line in text.splitlines():
        m = re.match(r'^\s*SSID\s+\d+\s*:\s*(.*)',line,re.I)
        if m:
            flush(); ssid = m.group(1).strip() or '<hidden>'
            continue
        m = re.match(r'^\s*BSSID\s+\d+\s*:\s*([0-9a-f:]{17})', line,re.I)
        if m:
            flush(); current = {'ssid':ssid,'bssid':m.group(1)}
            continue
        if current is None: continue
        m = re.match(r'^\s*(?:Signal|\u0627\u0644\u0625\u0634\u0627\u0631\u0629|\u0625\u0634\u0627\u0631\u0629)\s*:\s*(\d+)\s*%',line,re.I)
        if m: current['signal_percent']=min(100,int(m.group(1)))
        m = re.match(r'^\s*(?:Channel|\u0627\u0644\u0642\u0646\u0627\u0629|\u0642\u0646\u0627\u0629)\s*:\s*(\d+)',line,re.I)
        if m: current['channel']=int(m.group(1))
        m = re.match(r'^\s*(?:Radio type|\u0646\u0648\u0639 \u0627\u0644\u0631\u0627\u062f\u064a\u0648|\u0646\u0648\u0639 \u0627\u0644\u0644\u0627\u0633\u0644\u0643\u064a)\s*:\s*(.+)',line,re.I)
        if m: current['radio_type']=m.group(1).strip()
    flush()
    return {'available': proc.returncode == 0 and len(networks)>0,
            'reason': ('' if networks else ('No parsable Wi-Fi BSSIDs: enable a Wi-Fi adapter or check Windows locale')),
            'networks': networks[:100], 'survey_type': 'WINDOWS WLAN BSSID SCAN - NOT RF SPECTRUM',
            'count': len(networks)}
