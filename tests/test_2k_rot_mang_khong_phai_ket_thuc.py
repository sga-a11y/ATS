"""Leader ROT MANG giua thap 2K KHONG phai la "2K da xong" - va DIEU PHOI moi duoc chot.

Party 12 (06/09) - user: "danh deo danh, tu dung chay het ra ngoai roi thoat":

    13:50:11 [tonmot] 2K: da len tang 5 - Thang Thap (12928)
    13:50:40 [tonmot] 2K: xong tran idx=3, party song 0/0
    13:50:50 [tonmot] SERVER NGAT KET NOI: gui goi lien tuc qua nhanh (ma 13)
    13:50:50 [tonmot] (LEADER) 2K: ket thuc leo thap (xong/dung)     <- SAI: no bi DA, khong xong
    13:51:01 [tonmot] (LEADER) 2K da ket thuc -> ra khoi thap roi THOAT GAME
    13:51:22 qua cong idx=1 -> map 12927        \\
    13:51:47 qua cong idx=2 -> map 12926         | ca 5 acc di bo NGUOC 8 tang
    ...                                         /
    13:53:55 qua cong idx=1 -> map 12003        -> ra Quang Truong roi tat game

`run_floor_crawl` goi `on_done()` trong `finally`, tuc goi o CA BA duong thoat:
    thua tran | leo het thap/ket | CLIENT CHET GIUA CHUNG
Ban cu bam thang `st["event_exit_now"]` trong `on_done` nen ca ba deu thanh "2K xong".

HAI THU PHAI DUNG:
  1. `on_done` chi BAO SU THAT (`st["2k_ket_qua"]` = thua/xong/dut), khong tu quyet dinh gi.
  2. DIEU PHOI la noi DUY NHAT bat `event_exit_now` - dung luat "bot dieu phoi, khong phai acc
     nao ra lenh". Ket qua "dut" (client chet) ma con acc dang song -> KHONG thoat: supervisor
     relogin roi `_decide_2k_resume` leo tiep.
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _doc(*p):
    with io.open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


class _C:
    def __init__(self, running=True, map_id=12928):
        self.running = running
        self.current_map = map_id
        self.current_channel = 1


class TestChiDieuPhoiDuocChot(unittest.TestCase):
    PARTY = 3

    def setUp(self):
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)

    def tearDown(self):
        R._party_state.pop(self.PARTY, None)

    def test_ROT_MANG_thi_KHONG_thoat(self):
        self.st["2k_ket_qua"] = "dut"
        song = [("a1", _C(running=False)), ("a2", _C(running=True))]
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, song)
        self.assertFalse(self.st["event_exit_now"].is_set(),
                         "rot mang ma bat co thoat = ca party bi keo ra giua chung (party 12)")

    def test_KET_O_CONG_thi_KHONG_thoat(self):
        """Party 15 (06/09): leader dung 10 phut o tang 9 voi `chua du member (0/4)` ->
        `2K: ket o cong tang 9 (door=2) -> dung leo` -> ban truoc goi do la "xong" -> ca doi ra
        khoi thap + tat game. Ket o cong = CHUA het, phai gom + moi lai roi thu tiep."""
        self.st["2k_ket_qua"] = "ket"
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, [("a1", _C())])
        self.assertFalse(self.st["event_exit_now"].is_set())

    def test_THUA_thi_thoat(self):
        self.st["2k_ket_qua"] = "thua"
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, [("a1", _C())])
        self.assertTrue(self.st["event_exit_now"].is_set())

    def test_XONG_thi_thoat(self):
        self.st["2k_ket_qua"] = "xong"
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, [("a1", _C())])
        self.assertTrue(self.st["event_exit_now"].is_set())

    def test_chua_co_ket_qua_thi_khong_lam_gi(self):
        R._dieu_phoi_chot_2k_xong(self.PARTY, self.st, [("a1", _C())])
        self.assertFalse(self.st["event_exit_now"].is_set())

    def test_dieu_phoi_goi_ham_nay_o_pha_event(self):
        src = _doc("run_party_digioi.py")
        i = src.find("def _dieu_phoi_quyet(")
        than = src[i:src.find("\ndef ", i + 10)]
        self.assertIn("_dieu_phoi_chot_2k_xong(", than)


class TestLuongLeaderChiBaoSuThat(unittest.TestCase):
    def setUp(self):
        self.src = _doc("run_party_digioi.py")
        i = self.src.find("def _on_crawl_done(")
        self.than = self.src[i:self.src.find("def _heal_party_2k(", i)]

    def test_KHONG_tu_bat_co_thoat(self):
        self.assertNotIn('st["event_exit_now"].set()', self.than,
                         "luong leader tu quyet -> vi pham luat 'bot dieu phoi'")

    def test_chi_XONG_va_THUA_moi_la_het(self):
        self.assertIn('ly_do in ("xong", "thua")', self.than,
                      "gom ca 'ket'/'dut' vao la bo nham ca vong 2K")

    def test_nhan_LY_DO_tu_vong_leo_chu_khong_tu_doan(self):
        i = self.src.find("def _on_crawl_done(")
        self.assertIn("ly_do", self.src[i:i + 80])

    def test_CHUA_HET_thi_khong_danh_dau_da_danh_xong_event(self):
        """`event_battle_done` = 'khong mo lai nua' -> bat khi ket/dut la mat luon vong 2K."""
        i = self.than.find('st["event_battle_done"].set()')
        self.assertGreater(i, 0)
        self.assertIn("if _het:", self.than[:i])

    def test_CHI_MOT_noi_bat_event_exit_now(self):
        n = self.src.count('st["event_exit_now"].set()')
        self.assertEqual(n, 1, "co nhieu noi bat co thoat -> lai co acc tu quyet")
        i = self.src.find('st["event_exit_now"].set()')
        self.assertIn("_dieu_phoi_chot_2k_xong", self.src[:i][-1500:],
                      "noi bat co thoat phai nam trong ham cua dieu phoi")


class TestVongLeoBaoDungLyDo(unittest.TestCase):
    """`run_floor_crawl` phai noi RO vi sao dung, vi `finally` chay o MOI duong thoat."""

    def setUp(self):
        self.src = _doc("bot", "floor_crawl.py")

    def test_on_done_nhan_ly_do(self):
        self.assertIn("on_done(lost, ly_do)", self.src)

    def test_du_bon_ly_do(self):
        for tu in ('ly_do = "xong"', 'ly_do = "thua"', 'ly_do = "ket"', 'ly_do = "dut"'):
            self.assertIn(tu, self.src, tu)

    def test_toi_top_map_moi_la_XONG(self):
        i = self.src.find("da toi tang cao nhat")
        self.assertGreater(i, 0)
        self.assertIn('ly_do = "xong"', self.src[i:i + 200])

    def test_client_chet_thi_ghi_de_thanh_DUT(self):
        i = self.src.find("if not client.running:")
        self.assertGreater(i, 0, "khong xet client con song")
        self.assertIn('ly_do = "dut"', self.src[i:i + 200])

    def test_ket_o_cong_KHONG_dat_ly_do_xong(self):
        i = self.src.find("KET o cong")
        self.assertGreater(i, 0)
        khoi = self.src[i:i + 300]
        self.assertNotIn('ly_do =', khoi, "ket o cong phai giu ly_do mac dinh 'ket'")


class TestAPKGiongPC(unittest.TestCase):
    def test_apk_co_du(self):
        apk = _doc("android", "app", "src", "main", "python", "train_bot", "run_party_digioi.py")
        self.assertIn("def _dieu_phoi_chot_2k_xong(", apk)
        self.assertIn("on_done(lost, ly_do)",
                      _doc("android", "app", "src", "main", "python", "train_bot",
                           "floor_crawl.py"))


if __name__ == "__main__":
    unittest.main()
