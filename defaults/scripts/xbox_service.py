"""Xbox tab: the Xodus account service a game talks to while it runs.

Games get their Xbox identity (in-game sign-in, cloud saves, Store licence
checks) from `xodus-service`, reached through a loopback TCP bridge guarded
by a random key. Adapted from Xodus Nexus src/main/xodus-service.ts (MIT,
see third_party/xodus-nexus/LICENSE)."""

import hmac
import os
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import xbox_tools


class ServiceError(Exception):
    pass


class Bridge:
    """127.0.0.1:<port> → unix socket, after the client sends the key."""

    def __init__(self, socket_path):
        self.socket_path = str(socket_path)
        self.key = secrets.token_hex(32)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(16)
        self.port = self.server.getsockname()[1]
        self.closed = False
        self.sockets = set()
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self.closed:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(client,), daemon=True).start()

    def _serve(self, client):
        self.sockets.add(client)
        expected = self.key.encode("ascii")
        try:
            client.settimeout(10)
            got = b""
            while len(got) < len(expected):
                chunk = client.recv(len(expected) - len(got) + 4096)
                if not chunk:
                    return client.close()
                got += chunk
            if not hmac.compare_digest(got[:len(expected)], expected):
                return client.close()
            client.settimeout(None)
            up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            up.connect(self.socket_path)
            self.sockets.add(up)
            if got[len(expected):]:
                up.sendall(got[len(expected):])
            threading.Thread(target=self._pipe, args=(up, client), daemon=True).start()
            self._pipe(client, up)
        except OSError:
            client.close()

    @staticmethod
    def _pipe(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def stop(self):
        self.closed = True
        try:
            self.server.close()
        except OSError:
            pass
        for s in list(self.sockets):
            try:
                s.close()
            except OSError:
                pass


class Session:
    def __init__(self, proc, runtime_dir, bridge):
        self.proc, self.runtime_dir, self.bridge = proc, runtime_dir, bridge

    @property
    def env(self):
        return {"XODUS_SOCKET": str(Path(self.runtime_dir) / "xodus.sock"),
                "XODUS_BRIDGE_PORT": str(self.bridge.port), "XODUS_BRIDGE_KEY": self.bridge.key,
                "XODUS_SAVE_SYNC": "auto"}

    def stop(self):
        self.bridge.stop()
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(4)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        shutil.rmtree(self.runtime_dir, ignore_errors=True)


def _ready(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start(env, binary=None, timeout=90):
    """Start xodus-service in a private runtime dir and wait for its socket."""
    binary = binary or xbox_tools.service_path()
    if not binary:
        raise ServiceError("The Xbox account service is missing; reinstall the Xbox engine.")
    root = xbox_tools.XBOX_DIR / "service-sessions"
    root.mkdir(parents=True, exist_ok=True)
    runtime_dir = tempfile.mkdtemp(prefix="game-", dir=root)
    os.chmod(runtime_dir, 0o700)
    sock = Path(runtime_dir) / "xodus.sock"
    proc = subprocess.Popen([str(binary)], env=dict(env, XDG_RUNTIME_DIR=runtime_dir, XODUS_LOG="error"),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _ready(sock):
            return Session(proc, runtime_dir, Bridge(sock))
        if proc.poll() is not None:
            shutil.rmtree(runtime_dir, ignore_errors=True)
            raise ServiceError("The Xbox account service stopped; sign in again from the Xbox tab.")
        time.sleep(0.25)
    proc.kill()
    shutil.rmtree(runtime_dir, ignore_errors=True)
    raise ServiceError("The Xbox account service did not start in time.")
