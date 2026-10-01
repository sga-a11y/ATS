import unittest

from bot import client as C
from bot import region as R

# 2 goi S2C 0x02 sub0a THAT (captures/dienvi_server_20260721.pcap), them header 7B phia truoc.
_HDR = bytes.fromhex("c09100000000") + b"\x02"
CHAR = _HDR + bytes.fromhex("0a0003011c9e000002000e006400760069006e006e0061006d000270170000")
PET = _HDR + bytes.fromhex(
    "0a0003011c9e00000200160054006800e10069002000560003016e0020004300a10102d0070000")


def _mk():
    c = C.GameClient.__new__(C.GameClient)
    c._label = "t"
    c._exp_gain = {}
    c._exp_flush_timer = None
    c._schedule_exp_summary = lambda: None
    return c


class ExpKetTranTest(unittest.TestCase):
    def test_doc_goi_that_char_va_pet(self):
        self.assertEqual(C._parse_exp_broadcast(CHAR), ("dvinnam", 6000))
        nm, n = C._parse_exp_broadcast(PET)
        self.assertEqual(n, 2000)
        self.assertTrue(nm.startswith("Th"))

    def test_tsm_len_1_byte_big5(self):
        # captures/tsm_login_20260929.pcap: TSM ghi do dai ten 1 byte, chuoi Big5
        tsm = R.get("tsm")
        ch = _HDR + bytes.fromhex("0a0003011c9e000002000573746d6f740270170000")
        pet = _HDR + bytes.fromhex("0a0003011c9e0000020006bdb2a4e5ae5602d0070000")
        self.assertEqual(C._parse_exp_broadcast(ch, tsm), ("stmot", 6000))
        nm, n = C._parse_exp_broadcast(pet, tsm)
        self.assertEqual((len(nm), n), (3, 2000))

    def test_cau_khac_khong_phai_exp(self):
        khac = CHAR[:11] + (90230).to_bytes(4, "little") + CHAR[15:]
        self.assertIsNone(C._parse_exp_broadcast(khac))

    def test_tong_ket_cong_don_theo_ten(self):
        c = _mk()
        for p in (CHAR, PET, CHAR):
            c._add_exp_gain(*C._parse_exp_broadcast(p))
        txt = c._exp_summary_text()
        self.assertTrue(txt.startswith("EXP dvinnam +12000, "))
        self.assertTrue(txt.endswith(" +2000"))
        self.assertIsNone(c._exp_summary_text())

    def test_gui_an_ten_char_trong_dong_exp(self):
        import sys
        _argv, sys.argv = sys.argv, sys.argv[:1]   # gui -> run_party_digioi doc argv[1] luc import
        try:
            import gui
        finally:
            sys.argv = _argv
        g = gui.BotGUI.__new__(gui.BotGUI)
        g._privacy = 1
        g._ordinal = {"user1": "acc1"}
        g._char2user = {"chumuoi": "user1"}
        out = g._mask_log_line("08:28:09 [chumuoi] KET TRAN: EXP chumuoi +5, Quan Vu +464", "chumuoi")
        self.assertEqual(out, "08:28:09 [c***oi] KET TRAN: EXP c***oi +5, Quan Vu +464")


if __name__ == "__main__":
    unittest.main()
