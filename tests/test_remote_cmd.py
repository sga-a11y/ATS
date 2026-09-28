import os
import tempfile
import time
import unittest
from unittest import mock

from bot import remote_cmd as rc


def _l(s):
    b = s.encode("utf-16-le")
    return bytes([len(b)]) + b


def _whisper_pkt(sender_id, name, msg):
    """Goi S:002-003 dung cau truc crack (Chat.ReceiveMessage)."""
    body = sender_id + b"\x00\x00" + _l(name) + _l(msg) + b"\x00\x00"
    return b"\xc0\x91" + (9 + len(body)).to_bytes(2, "little") + b"\x00\x00\x02\x03\x00" + body


class ParseOffTest(unittest.TestCase):
    def test_hop_le(self):
        self.assertEqual(rc.parse_off("off 30p"), 30)
        self.assertEqual(rc.parse_off("  OFF 5P "), 5)
        self.assertEqual(rc.parse_off("off 600p"), 600)

    def test_sai(self):
        for t in ("off 30", "off 0p", "off 601p", "off 30h", "lekha off 30p", "off", "", None):
            self.assertIsNone(rc.parse_off(t), t)


class WhitelistTest(unittest.TestCase):
    def test_khop_khong_phan_biet_hoa_thuong(self):
        self.assertTrue(rc.is_allowed("Hoàng Anh", ["hoàng anh"]))
        self.assertFalse(rc.is_allowed("hoang anh", ["hoàng anh"]))

    def test_rong_la_khong_ai_duoc(self):
        self.assertFalse(rc.is_allowed("abc", []))
        self.assertFalse(rc.is_allowed("", [""]))


class PacketTest(unittest.TestCase):
    def test_parse_whisper(self):
        sid = bytes(range(1, 9))
        got = rc.parse_whisper(_whisper_pkt(sid, "Hoàng Anh", "off 30p"))
        self.assertEqual(got, (sid, "Hoàng Anh", "off 30p"))

    def test_build_roi_parse_lai(self):
        sid = bytes(range(8))
        p = rc.build_whisper(sid, "Tên", "OK off 30p")
        self.assertEqual(p[:2], b"\x03\x00")
        self.assertEqual(p[2:10], sid)
        self.assertEqual(p[-2:], b"\x00\x00")
        # cung layout voi goi nhan, tru titleId -> chen 2 byte de dung lai parser
        fake = b"\xc0\x91\x00\x00\x00\x00\x02" + p[:10] + b"\x00\x00" + p[10:]
        self.assertEqual(rc.parse_whisper(fake)[1:], ("Tên", "OK off 30p"))


class OffStateTest(unittest.TestCase):
    def test_luu_va_xoa(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(rc, "_state_path", lambda: os.path.join(d, "off.json")):
                self.assertEqual(rc.off_remaining("a"), 0)
                rc.set_off(["a", "b"], time.time() + 60)
                self.assertGreater(rc.off_remaining("a"), 50)
                rc.clear_off("a")
                self.assertEqual(rc.off_remaining("a"), 0)
                self.assertGreater(rc.off_remaining("b"), 50)


if __name__ == "__main__":
    unittest.main()
