import os
import socket
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

FAKE_SERVICE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import os, socket, signal, sys
    path = os.path.join(os.environ["XDG_RUNTIME_DIR"], "xodus.sock")
    if os.environ.get("FAKE_FAIL"):
        sys.exit(1)
    s = socket.socket(socket.AF_UNIX); s.bind(path); s.listen(4)
    signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
    while True:
        c, _ = s.accept()
        try:
            data = c.recv(100)
            if data:
                c.sendall(b"echo:" + data)
        except OSError:
            pass
        c.close()
""")


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["DECKY_PLUGIN_RUNTIME_DIR"] = self.tmp.name
        import importlib
        import xbox_tools
        import xbox_service
        importlib.reload(xbox_tools)
        self.s = importlib.reload(xbox_service)
        self.fake = Path(self.tmp.name) / "fake-service"
        self.fake.write_text(FAKE_SERVICE)
        self.fake.chmod(0o755)

    def connect(self, port, payload):
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(payload)
        try:
            return c.recv(100)
        except OSError:
            return b""
        finally:
            c.close()

    def test_session_env_and_bridge_round_trip(self):
        session = self.s.start(dict(os.environ), binary=self.fake, timeout=10)
        try:
            env = session.env
            self.assertTrue(env["XODUS_SOCKET"].endswith("xodus.sock"))
            self.assertEqual(env["XODUS_SAVE_SYNC"], "auto")
            reply = self.connect(int(env["XODUS_BRIDGE_PORT"]), env["XODUS_BRIDGE_KEY"].encode() + b"hi")
            self.assertEqual(reply, b"echo:hi")
        finally:
            session.stop()
        self.assertIsNotNone(session.proc.poll())
        self.assertFalse(Path(session.runtime_dir).exists())

    def test_wrong_key_is_rejected(self):
        session = self.s.start(dict(os.environ), binary=self.fake, timeout=10)
        try:
            reply = self.connect(session.bridge.port, b"x" * 64 + b"hi")
            self.assertEqual(reply, b"")
        finally:
            session.stop()

    def test_service_exit_reported(self):
        with self.assertRaises(self.s.ServiceError):
            self.s.start(dict(os.environ, FAKE_FAIL="1"), binary=self.fake, timeout=10)

    def test_bridge_only_on_loopback(self):
        session = self.s.start(dict(os.environ), binary=self.fake, timeout=10)
        try:
            self.assertEqual(session.bridge.server.getsockname()[0], "127.0.0.1")
        finally:
            session.stop()


if __name__ == "__main__":
    unittest.main()
