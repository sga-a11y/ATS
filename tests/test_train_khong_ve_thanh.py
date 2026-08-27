# -*- coding: utf-8 -*-
"""MODE TRAIN: ca party DA o map train roi thi KHONG teleport ve thanh de keo len lai.

User chot 27/08:
  "cung o map train roi thi check kenh, neu cung kenh roi thi lap party keo ra train,
   ko cung kenh thi sync kenh thoi, ko can ve thanh"
  "ca reform va ca di train luc dau"

Truoc day moi lan thieu nguoi trong party (moi 20s chua du, cho member san sang qua lau, reform_gen
tang...) la _do_reform() -> CA PARTY teleport ve thanh roi di route len lai, du tat ca dang dung
san o bai train. Mat vai phut moi vong va de lac them nguoi giua duong.
"""
import io
import os
import unittest

import run_party_digioi as rp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestPhanLoaiTaiCho(unittest.TestCase):
    def test_cung_map_train_cung_kenh(self):
        self.assertEqual(rp._party_train_tai_cho([700, 700, 700], [2, 2, 2], 700), "cung_kenh")

    def test_cung_map_train_lech_kenh(self):
        self.assertEqual(rp._party_train_tai_cho([700, 700], [2, 3], 700), "lech_kenh")

    def test_co_dua_o_map_khac(self):
        self.assertEqual(rp._party_train_tai_cho([700, 12061], [2, 2], 700), "lech_map")

    def test_ca_party_o_map_KHAC_train_van_la_lech_map(self):
        """Cung nhau o nham map (vd ca lu con trong thanh) thi VAN phai gom ve, khong lap party."""
        self.assertEqual(rp._party_train_tai_cho([12061, 12061], [1, 1], 700), "lech_map")

    def test_chua_biet_kenh_thi_coi_la_LECH(self):
        """Doc chua ra kenh ma dam ket luan 'cung kenh' la lap party xong moi khong toi noi."""
        self.assertEqual(rp._party_train_tai_cho([700, 700], [2, None], 700), "lech_kenh")

    def test_khong_co_du_lieu_thi_khong_dam_xu_ly_tai_cho(self):
        self.assertEqual(rp._party_train_tai_cho([], [], 700), "lech_map")
        self.assertEqual(rp._party_train_tai_cho([700], [1], 0), "lech_map")


class TestApVaoLuong(unittest.TestCase):
    def test_co_ham_xu_ly_tai_cho(self):
        s = _src()
        self.assertIn("def _party_tai_cho_xu_ly(", s)
        i = s.find("def _party_tai_cho_xu_ly(")
        than = s[s.find('"""', s.find('"""', i) + 3) + 3:i + 2200]   # bo docstring
        self.assertIn("do_channel_sync()", than, "lech kenh -> sync kenh tai cho")
        self.assertNotIn("_do_reform", than, "xu ly tai cho KHONG duoc ve thanh")

    def test_ap_cho_MOI_cho_reform_cua_train(self):
        """Ca luc moi di train lan cac vong reform ve sau - user dan 'ca reform va ca di train'."""
        s = _src()
        self.assertGreaterEqual(s.count("_party_tai_cho_xu_ly("), 6)
        for moc in ("luc di train", "moi %.0fs chua du party", "cho member san sang",
                    "reform gen %d", "sau reconnect", "lenh tay"):
            self.assertIn(moc, s, "thieu cho ap luat tai cho: %s" % moc)

    def test_xu_ly_tai_cho_phai_BAT_LAI_DANH(self):
        """Caller (reform / lenh doi kenh tay) dat flee_mode=True de di duong. Nhanh _do_reform
        ket thuc bang combat_ready()+flee_mode=False; nhanh tai cho quen thi bot dung dung diem
        quai ma cu bo chay, khong danh con nao."""
        s = _src()
        i = s.find("def _party_tai_cho_xu_ly(")
        doan = s[i:i + 2600]
        self.assertIn("c.combat_ready()", doan)
        self.assertIn("c.flee_mode = False", doan)

    def test_sync_kenh_CHUA_XONG_thi_KHONG_moi_party(self):
        """Moi party luc con lech kenh = loi moi khong toi noi, party mai khong du."""
        s = _src()
        i = s.find("def _party_tai_cho_xu_ly(")
        doan = s[i:i + 3000]
        self.assertIn("if not do_channel_sync():", doan)
        j = doan.find("if not do_channel_sync():")
        nhanh = doan[j:doan.find("else:", j)]
        self.assertIn("return True", nhanh, "van la 'da xu ly tai cho' - KHONG ve thanh")
        self.assertNotIn("_invite_party_participants", nhanh)

    def test_leader_moi_lai_NGAY_khong_doi_60s(self):
        s = _src()
        i = s.find("def _party_tai_cho_xu_ly(")
        self.assertIn("_invite_party_participants(c, train_on_map, gap=1.0)", s[i:i + 3200])

    def test_RA_SAFE_truoc_khi_doi_kenh(self):
        """User 27/08: "phai chay ra diem an toan roi moi switch chu".

        Doi kenh giu nguyen map/toa do, ma party vua tan (leave_party truoc khi doi) -> doi ngay
        giua bay quai la tung acc dung le an dan khi vao kenh moi.
        """
        s = _src()
        self.assertIn("def _ra_safe_truoc_khi_doi_kenh(", s)
        i = s.find("def _ra_safe_truoc_khi_doi_kenh(")
        than = s[s.find('"""', s.find('"""', i) + 3) + 3:i + 1600]
        self.assertIn("c.navigate_to(", than)
        self.assertIn('st.get("rally_point")', than)
        # Ca 2 duong doi kenh deu phai goi: lenh tay tu GUI va sync kenh trong luong
        self.assertIn('_ra_safe_truoc_khi_doi_kenh("lenh doi kenh tay")', s)
        self.assertIn('_ra_safe_truoc_khi_doi_kenh("sync kenh")', s)

    def test_ra_safe_goi_TRUOC_switch_channel(self):
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 500]
        self.assertLess(doan.find("_ra_safe_truoc_khi_doi_kenh"), doan.find("c.switch_channel("),
                        "phai ra safe TRUOC khi doi kenh")

    def test_van_ve_thanh_khi_dang_gom_nhau_o_thanh(self):
        """reform_arrived co entry = co nguoi DANG DUNG CHO o thanh -> ve gop that, khong bo roi ho."""
        s = _src()
        i = s.find("_gather_wait_me = bool(_gather)")
        doan = s[i:i + 900]
        self.assertIn("not _gather_wait_me", doan)


class TestSyncKenhPhaiCheckKenh(unittest.TestCase):
    """User hoi 27/08: "luc dong bo kenh m da check cung kenh roi moi moi party chua".

    Barrier cua do_channel_sync von CHI kiem MAP. No con co duong tat: leader doc map LIVE cua
    tung acc va tu tinh la "xong" ma khong can acc do bao cao - duong tat do bo qua KENH, nen acc
    dang ban viec khac (map dung, chua he doi kenh) van duoc tinh la xong -> sync bao OK -> MOI
    PARTY trong khi no o kenh khac -> loi moi khong bao gio toi.
    """

    def test_duong_tat_phai_xet_ca_kenh(self):
        s = _src()
        i = s.find("_live_ch[_u] = getattr(_uc")
        self.assertGreater(i, 0, "phai doc ca current_channel cua tung acc")
        doan = s[i:i + 1400]
        self.assertIn('_ch_chot = st.get("channel")', doan)
        self.assertIn("int(_uch) != _ch_chot", doan)
        self.assertIn("continue", doan)

    def test_giu_nguyen_1_kenh_thi_khong_so_kenh(self):
        """ch = 0 = server chi co 1 kenh (hoac co nick tay -> giu nguyen) -> khong co gi de so."""
        s = _src()
        i = s.find("_ch_chot = int(_ch_chot) if _ch_chot else 0")
        self.assertGreater(i, 0)
        self.assertIn("if _ch_chot:", s[i:i + 400])

    def test_lech_kenh_phai_LOG_RO_ten_acc(self):
        """Truoc day chi thay "cho acc bao cao map (3/5)" - khong biet ai, kenh nao."""
        s = _src()
        self.assertIn("CHUA sang: %s", s)
        self.assertIn("_lech_ch = {_u: _live_ch.get(_u)", s)


if __name__ == "__main__":
    unittest.main()
