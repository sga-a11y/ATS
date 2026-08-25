# -*- coding: utf-8 -*-
"""Neo ma chon cua cau Gioi kieu THANG vao capture client that.

`captures/gioikieu_20260825.pcap` - user tu bam trong client that o cong 10 map 63000:
2 lan bam "khong danh", lan 3 bam "danh" roi vao tran.

    0x14 08 0a00 -> 0x14 09 001f (31) -> 0x14 06          khong danh
    0x14 08 0a00 -> 0x14 09 001f (31) -> 0x14 06          khong danh
    0x14 08 0a00 -> 0x14 09 001e (30) -> 0x14 06 -> 0x32  DANH -> vao tran

=> 30 = danh (muc 1 danh sach), 31 = khong danh (muc 2). KHONG phai hop Co/Khong.
Ma 20 tung bi doan nham -> server tra "su kien vi pham" roi NGAT KET NOI.
"""
import os
import unittest

PCAP = os.path.join("captures", "gioikieu_20260825.pcap")


def _c2s_frames():
    """Doc frame C2S tu pcap (XOR 0xAD, khung c0 91) - khong phu thuoc analyze_pcap."""
    import struct
    with open(PCAP, "rb") as fh:
        data = fh.read()
    out = []
    # duyet tho: tim moi chuoi da giai XOR bat dau bang c0 91 trong toan bo file
    dec = bytes(b ^ 0xAD for b in data)
    i = 0
    while True:
        i = dec.find(b"\xc0\x91", i)
        if i < 0:
            break
        if i + 4 <= len(dec):
            ln = struct.unpack_from("<H", dec, i + 2)[0]
            if 7 <= ln <= 4096 and i + ln <= len(dec):
                out.append(dec[i:i + ln])
        i += 2
    return out


class TestGioiKieuCapture(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(PCAP):
            self.skipTest("chua co %s" % PCAP)

    def test_capture_co_ma_30_va_31(self):
        """Capture phai chua CA HAI ma - neu khong thi file da bi thay, dung tin ket luan nua."""
        frames = _c2s_frames()
        chon = [f[9] for f in frames
                if len(f) >= 10 and f[6] == 0x14 and f[7] == 0x09 and f[8] == 0x00]
        self.assertIn(30, chon, "capture phai co ma 30 (danh)")
        self.assertIn(31, chon, "capture phai co ma 31 (khong danh)")

    def test_bot_thu_ma_30_truoc(self):
        """Bot phai thu ma DANH dau tien - do la ma duy nhat qua duoc cau."""
        from bot.client import GameClient
        self.assertEqual(GameClient.GATE_CHOICE_CODES[0], 30)

    def test_bot_khong_dat_ma_20_len_dau(self):
        """Ma 20 lam server NGAT KET NOI o cua nay -> khong duoc thu dau tien."""
        from bot.client import GameClient
        self.assertNotEqual(GameClient.GATE_CHOICE_CODES[0], 20)


if __name__ == "__main__":
    unittest.main()
