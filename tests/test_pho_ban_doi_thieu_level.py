"""PB to doi: chua du cap thi BO QUA, va PB hong KHONG duoc lam mat o 1 cua nhiem vu ngay.

User chot 02/09 (soi party 19 quan_vu cuoi ngay):
  - "bon no hong vi lv ko du, moi lv 68 ko di duoc PB 80" -> "neu ko du level thi bo qua PB do".
  - "gio cuoi ngay roi, ... neu van con acc ko xong quest thi la bot ngu".

HAI loi doc lap nhau:

1) KHONG check cap truoc khi tao phong. Server khong cho acc duoi cap READY, nen bot cu tao phong
   roi cho 40s: "lv80 member ready 0/4 sau 40.1s -> HUY phong, relogin ca party" - lap lai MOI chu ky
   (23:34:50 va 23:42:09 deu y het).

2) `_finish_digioi_train_if_time_over`: PB hong -> `return True` NGAY, ma `do_daily_dungeon()` (o 1)
   nam NGAY DUOI cai return do -> o 1 khong bao gio duoc lam. Pha train cung khong va lai duoc vi
   `_do_startup_daily` chi goi `claim_daily_quests`, KHONG goi `do_daily_dungeon`.
   Ket qua do duoc: cuoi ngay 6 acc (quan808/809/810, qv801/802, dt803) dung o `o xong=[2..9]` -
   du 8/9, thieu DUNG o 1.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# run_party_digioi doc sys.argv[1] lam so PHUT ngay luc import; ten module cua unittest loi vao do.
_argv = sys.argv
sys.argv = [_argv[0]]
try:
    import run_party_digioi as rpd    # noqa: E402
finally:
    sys.argv = _argv


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestThieuLevel(unittest.TestCase):
    def _st(self, **lv):
        return {"char_level_by": dict(lv)}

    def test_duoi_cap_thi_bao_thieu(self):
        st = self._st(a=68, b=68)
        self.assertEqual(rpd._thieu_level(st, ["a", "b"], 80), [("a", 68), ("b", 68)])

    def test_du_cap_thi_khong_thieu(self):
        st = self._st(a=80, b=95)
        self.assertEqual(rpd._thieu_level(st, ["a", "b"], 80), [])

    def test_BANG_dung_cap_la_DU(self):
        """PB lv80 can cap >= 80 -> dung 80 la vao duoc."""
        self.assertEqual(rpd._thieu_level(self._st(a=80), ["a"], 80), [])

    def test_CHI_MOT_dua_thieu_cung_tinh(self):
        st = self._st(a=99, b=68, c=99)
        self.assertEqual(rpd._thieu_level(st, ["a", "b", "c"], 80), [("b", 68)])

    def test_CHUA_biet_cap_thi_KHONG_bo_oan(self):
        """Chua doc duoc goi 0x05 -> tha cho thu, con hon bo nham PB dang lam duoc."""
        self.assertEqual(rpd._thieu_level(self._st(), ["a"], 80), [])
        self.assertEqual(rpd._thieu_level(self._st(a=99), ["a", "b"], 80), [])

    def test_PB_thap_van_danh_duoc_khi_cap_thap(self):
        st = self._st(a=68, b=68)
        self.assertEqual(rpd._thieu_level(st, ["a", "b"], 20), [])
        self.assertEqual(rpd._thieu_level(st, ["a", "b"], 50), [])
        self.assertTrue(rpd._thieu_level(st, ["a", "b"], 80))
        self.assertTrue(rpd._thieu_level(st, ["a", "b"], 110))


class TestBaoCapNhanVat(unittest.TestCase):
    def test_state_co_cho_luu(self):
        self.assertIn('"char_level_by": {},', _src())

    def test_moi_acc_bao_cap_luc_vao_PB(self):
        src = _src()
        i = src.find("reports[username] = remaining")
        self.assertGreater(i, 0)
        khoi = src[i:i + 400]
        self.assertIn('getattr(c, "char_level", None)', khoi)
        self.assertIn('st.setdefault("char_level_by", {})[username]', khoi)

    def test_cap_0_hoac_None_thi_KHONG_ghi(self):
        """Ghi 0 vao thi moi PB deu bi coi la thieu cap -> bo sach."""
        src = _src()
        i = src.find('_lv = getattr(c, "char_level", None)')
        self.assertIn("if _lv:", src[i:i + 160])


class TestLeaderBoQuaTierThieuCap(unittest.TestCase):
    def setUp(self):
        self.src = _src()

    def test_co_kiem_truoc_khi_tao_phong(self):
        """Tao phong = `_handle_auto_team_dungeon` goi xuong client (`=== PHO BAN TO DOI LV%d ===`).
        Kiem cap phai xong TRUOC do, khong thi van ton 40s cho ready roi moi biet."""
        i = self.src.find("_thieu = _thieu_level(st, members, level)")
        self.assertGreater(i, 0, "leader khong he kiem cap")
        sau = self.src[i:]
        i_run = sau.find("c.do_team_dungeon(level)")
        self.assertGreater(i_run, 0, "khong tim thay cho leader chay PB sau buoc kiem cap")

    def test_bo_qua_thi_danh_dau_done_de_member_khong_cho_mai(self):
        i = self.src.find("_thieu = _thieu_level(st, members, level)")
        khoi = self.src[i:i + 700]
        self.assertIn('st.setdefault("team_dungeon_state", {})[level] = "done"', khoi)
        self.assertIn("return True", khoi)

    def test_log_noi_ro_acc_nao_thieu_bao_nhieu(self):
        i = self.src.find("_thieu = _thieu_level(st, members, level)")
        khoi = self.src[i:i + 700]
        self.assertIn("chưa đủ cấp", khoi)
        self.assertIn("lv%d", khoi)


class TestPBHongKhongLamMatO1(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        i = self.src.find("_maybe_auto_world_boss(\"sau DG, truoc pho ban doi\")")
        self.assertGreater(i, 0)
        self.than = self.src[i:i + 3000]

    def test_PB_hong_KHONG_return_som(self):
        i_hong = self.than.find("pho ban to doi khong xong")
        i_daily = self.than.find("c.do_daily_dungeon()")
        self.assertGreater(i_hong, 0)
        self.assertGreater(i_daily, 0)
        giua = re.sub(r"#.*", "", self.than[i_hong:i_daily])
        self.assertNotIn("return", giua,
                         "PB doi hong van chan o 1 (phó bản solo) nhu bug 02/09")

    def test_VAN_chuyen_pha_train(self):
        """Bo `return` som khong duoc lam mat viec chuyen pha."""
        i_daily = self.than.find("c.do_daily_dungeon()")
        self.assertIn('_dt["relogin_train"] = True', self.than[i_daily:i_daily + 1200])

    def test_VAN_claim_nhiem_vu_ngay(self):
        i_daily = self.than.find("c.do_daily_dungeon()")
        self.assertIn("c.claim_daily_quests(heavy=True)", self.than[i_daily:i_daily + 500])


if __name__ == "__main__":
    unittest.main()
