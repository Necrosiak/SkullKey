#!/usr/bin/env python3
"""Deliver Maxima's sign-in URL to its private GUI socket, never to a log."""
import os
from pathlib import Path
import socket
import stat
import sys
from urllib.parse import urlsplit


def deliver(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "accounts.ea.com"
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443) or len(url.encode()) > 32768):
        raise ValueError("Unexpected login destination")
    path = Path(os.environ["SK_EA_LOGIN_SOCKET"])
    parent = path.parent.stat()
    info = path.lstat()
    if (parent.st_uid != os.getuid() or parent.st_mode & 0o077
            or info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode)
            or info.st_mode & 0o077):
        raise ValueError("Unsafe login socket")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(10)
        client.connect(str(path))
        client.sendall(url.encode())


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("One login URL required")
        deliver(sys.argv[1])
    except Exception:
        sys.exit(1)
