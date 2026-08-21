"""Co NHIEM VU (MarkManager.flags) phai doc theo chi so 1-BASED y het client.

Bug that (party.log 21/08 22:58): bot bao hoan thanh thanh tuu roi bi server tu choi lien tiep:
  Thanh tuu: bao hoan thanh 'Tấn Công Địch Thủ' (id=204) BI TU CHOI - DIEU KIEN KHONG DU
  ... id 300, 336, 388, 390 - TAT CA deu kind=15 (MissionFlag)
  Thanh tuu: server tu choi 5 cai LIEN TIEP -> DUNG bao hoan thanh

Goc re: mark_flag_get dung `bitId // 8` va `bitId % 8` (0-based), trong khi client dung 1-based:
  functions.lua CheckFlag:  tableIndex = (flagIndex - 1) // 8 + 1
                            bit trong byte = (flagIndex - 1) % 8
  MarkManager.InitMissionFlag: `this.flags[index] = ReadByte()` -> khoa byte server gui la 1-BASED
=> doc nham sang co cua nhiem vu KHAC -> duong tinh gia -> bao bua -> server tu choi.

Chu thich ham do con ghi "giong BitFlag 0x51", nhung _bitflag_get moi la ban lam DUNG.
"""
import random
import unittest
from pathlib import Path

from bot.client import GameClient

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "bot/client.py").read_text(encoding="utf-8")


def check_flag_lua(flags, idx):
    """Ban Python trung thanh cua CheckFlag (Common/functions.lua) - lam CHUAN doi chieu."""
    if idx < 1:
        return False
    t = (idx - 1) // 8 + 1
    if t not in flags:
        return False
    return bool(flags[t] & (1 << ((idx - 1) % 8)))


def check_flag_cu(flags, idx):
    """Cong thuc SAI truoc khi sua - giu lai de chung minh bug co that."""
    return bool(flags.get(idx // 8, 0) & (1 << (idx % 8)))


def client_voi(flags):
    o = GameClient.__new__(GameClient)
    o.mark_flags = dict(flags)
    return o


class TestMarkFlagBitBase(unittest.TestCase):
    def test_khop_100_phan_tram_voi_client(self):
        random.seed(7)
        flags = {k: random.randrange(256) for k in range(1, 200)}
        o = client_voi(flags)
        sai = [b for b in range(1, 1500) if check_flag_lua(flags, b) != o.mark_flag_get(b)]
        self.assertEqual(sai, [], "lech so voi CheckFlag cua client o %d bit" % len(sai))

    def test_cong_thuc_CU_that_su_sai_va_sinh_duong_tinh_gia(self):
        """Chung minh bug co that: ban cu doc sai ~1/2 so bit, nhieu cai la duong tinh gia."""
        random.seed(7)
        flags = {k: random.randrange(256) for k in range(1, 200)}
        sai = [b for b in range(1, 1500) if check_flag_lua(flags, b) != check_flag_cu(flags, b)]
        gia = [b for b in range(1, 1500)
               if check_flag_cu(flags, b) and not check_flag_lua(flags, b)]
        self.assertGreater(len(sai), 300)
        self.assertGreater(len(gia), 100, "duong tinh gia = bot bao bua -> server tu choi")

    def test_bit_0_va_am_khong_lam_sap(self):
        o = client_voi({1: 0xFF})
        self.assertFalse(o.mark_flag_get(0))
        self.assertFalse(o.mark_flag_get(-5))

    def test_duong_GHI_cung_1_based(self):
        """S:024-005 cap nhat theo CHI SO BIT - phai ghi cung he voi luc doc."""
        self.assertIn("bidx, mask = (bit - 1) // 8 + 1, 1 << ((bit - 1) % 8)", SRC)

    def test_doc_ghi_di_doi_nhau(self):
        """Ghi bit N roi doc bit N phai ra True; bit ben canh phai ra False."""
        o = client_voi({})
        for bit in (1, 7, 8, 9, 16, 17, 100):
            o.mark_flags = {}
            b = bit - 1
            o.mark_flags[b // 8 + 1] = 1 << (b % 8)      # ghi y het duong sub-05 da sua
            self.assertTrue(o.mark_flag_get(bit), "bit %d ghi roi doc khong ra" % bit)
            self.assertFalse(o.mark_flag_get(bit + 1), "bit %d ro ri sang bit ben canh" % bit)


if __name__ == "__main__":
    unittest.main()
