import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "defaults" / "scripts"))

import xbox_updates as U


def serve(path, reply, seen):
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)

    def run():
        c, _ = srv.accept()
        head = c.recv(8)
        magic, kind, length = struct.unpack("<IHH", head)
        seen.append((magic, kind, c.recv(length).decode()))
        body = reply.encode()
        c.sendall(struct.pack("<IHH", 0x58445358, 10, len(body)) + body)
        c.close()
        srv.close()
    threading.Thread(target=run, daemon=True).start()


class UpdatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sock = os.path.join(self.tmp.name, "x.sock")

    def test_newer_version_available(self):
        seen = []
        serve(self.sock, "<Reply><LatestVersion>1.0.57.0</LatestVersion><HResult>0</HResult><Checked>true</Checked></Reply>", seen)
        r = U.query(self.sock, "9P74BRFBXXC6", "1.0.56.0")
        self.assertEqual(r, {"available": True, "latest": "1.0.57.0"})
        self.assertEqual(seen[0][:2], (0x58445358, 9))
        self.assertIn("<ProductId>9P74BRFBXXC6</ProductId>", seen[0][2])

    def test_up_to_date(self):
        serve(self.sock, "<R><LatestVersion>1.0.56.0</LatestVersion><HResult>0</HResult><Checked>true</Checked></R>", [])
        self.assertEqual(U.query(self.sock, "9P74BRFBXXC6", "1.0.56.0")["available"], False)

    def test_version_comparison_stage_accepted(self):
        xml = f"<R><LatestVersion>2.0.0.0</LatestVersion><HResult>{0x80004001}</HResult><ErrorStage>version-comparison</ErrorStage></R>"
        self.assertTrue(U.result(xml, "1.0.0.0")["available"])

    def test_unverified_reply_is_an_error(self):
        self.assertIn("error", U.result("<R><HResult>5</HResult></R>", "1.0.0.0"))
        self.assertIn("error", U.query(self.sock, "bad", "1.0.0.0"))

    def test_installed_version_from_manifest(self):
        d = Path(self.tmp.name) / "g"
        d.mkdir()
        (d / "MicrosoftGame.Config").write_text('<Game><Identity Name="A" Publisher="B" Version="1.0.56.0"/></Game>')
        self.assertEqual(U.installed_version(d), "1.0.56.0")


if __name__ == "__main__":
    unittest.main()
