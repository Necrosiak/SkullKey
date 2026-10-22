"""Xbox tab: is a newer version of an installed game available?

Asks the Xodus account service with the request Xodus Nexus uses
(src/main/game-updates.ts, MIT): a 8-byte header (magic "XSDX", kind 9,
body length) followed by <Request><ProductId/><InstalledVersion/></Request>."""

import re
import socket
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

MAGIC = 0x58445358
VERSION = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _version(value):
    if not value or not VERSION.match(value):
        return None
    parts = [int(p) for p in value.split(".")]
    return parts if all(p <= 65535 for p in parts) else None


def installed_version(root):
    root = Path(root)
    for name in ("microsoftgame.config", "appxmanifest.xml"):
        f = next((p for p in root.iterdir() if p.name.lower() == name), None) if root.is_dir() else None
        if not f:
            continue
        try:
            tree = ET.fromstring(f.read_text(errors="ignore"))
        except ET.ParseError:
            continue
        for el in tree.iter():
            if el.tag.rsplit("}", 1)[-1] == "Identity" and _version(el.get("Version")):
                return el.get("Version")
    return None


def _value(xml, key):
    m = re.search(rf"<{key}>([^<]*)</{key}>", xml)
    return m.group(1) if m else None


def result(xml, installed):
    """{"available": bool, "latest": str} or {"error": str}."""
    latest = _value(xml, "LatestVersion")
    left, right = _version(installed), _version(latest)
    hr_text = _value(xml, "HResult") or ""
    hr = int(hr_text) if hr_text.isdigit() else None
    ok = (hr == 0 and _value(xml, "Checked") == "true") or (hr == 0x80004001 and _value(xml, "ErrorStage") == "version-comparison")
    if not left or not right or not ok:
        return {"error": "update availability could not be verified"}
    return {"available": right > left, "latest": latest}


def query(socket_path, product_id, installed, timeout=65):
    if not re.match(r"^[A-Z0-9]{12}$", product_id, re.I) or not _version(installed):
        return {"error": "a Store id and a four-part version are required"}
    body = f"<Request><ProductId>{product_id}</ProductId><InstalledVersion>{installed}</InstalledVersion></Request>".encode()
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(socket_path))
        s.sendall(struct.pack("<IHH", MAGIC, 9, len(body)) + body)
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                return {"error": "the update service closed before replying"}
            buf += chunk
            if len(buf) >= 8:
                magic, kind, length = struct.unpack("<IHH", buf[:8])
                if magic != MAGIC or kind not in (9, 10):
                    return {"error": "unsupported update service response"}
                if len(buf) >= 8 + length:
                    return result(buf[8:8 + length].decode("utf-8", "replace"), installed)
    except OSError as e:
        return {"error": f"update check failed ({type(e).__name__})"}
    finally:
        s.close()
