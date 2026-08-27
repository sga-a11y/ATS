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
        self.assertIn("_bat_danh_neu_du_party()", doan)

    def test_CHUA_DU_PARTY_thi_KHONG_danh(self):
        """User 27/08: "lam lon gi ma leader danh 1 minh". Party vua bi giai tan de lap lai ->
        bat danh vo dieu kien la leader dam quai mot minh giua bai, pham nguyen tac
        "DU FULL PARTY MOI TRAIN". _do_reform lam dung: `c.flee_mode = not _full`.
        """
        s = _src()
        i = s.find("def _bat_danh_neu_du_party():")
        self.assertGreater(i, 0)
        than = s[s.find('"""', s.find('"""', i) + 3) + 3:i + 1400]
        self.assertIn("joined_member_count(pidx) >= st[\"n_members\"]", than)
        self.assertIn("c.flee_mode = not _full", than)
        self.assertIn("if _full:", than)
        # combat_ready phai NAM TRONG nhanh _full
        self.assertLess(than.find("if _full:"), than.find("c.combat_ready()"))

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

    def test_KHONG_doi_kenh_giua_tran(self):
        """User 27/08: "party dang trong battle va ko doi kenh duoc nhung bot bao doi kenh thanh
        cong". Vong cho ket tran o tren cap 60s roi BREAK, va van gui switch_channel giua tran.
        Train thi party danh lien tuc -> gan nhu luon roi vao canh do.
        """
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 2600]
        self.assertIn("c._wait_combat_clear(idle=2.0, cap=120.0)", doan)
        self.assertIn("VAN dang trong tran -> chua doi kenh", doan)
        # phai CHUA doi kenh khi con in_combat -> co continue truoc switch_channel
        j = doan.find("c.in_combat(idle_secs=3.0)")
        self.assertGreater(j, 0)
        self.assertLess(j, doan.find("c.switch_channel("), "check tran phai TRUOC switch_channel")

    def test_doi_kenh_that_bai_thi_KHONG_bao_thanh_cong(self):
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 4400]
        self.assertIn("GIU kenh cu", doan)
        # st["channel"] chi duoc ghi khi ok
        k = doan.find('st["channel"] = int(ch)')
        self.assertGreater(k, 0)
        self.assertIn("if ok:", doan[max(0, k - 120):k])

    def test_kien_tri_chu_khong_bo_som(self):
        """User 27/08: "roi sau do the nao, bot do luon a". Bo sau vai lan = lenh cua user bi nuot
        im, vi dang train thi tran noi tiep tran nen vai lan dau chac chan roi vao giua tran."""
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 3600]
        self.assertIn("_han = time.time() + 300", doan, "kien tri toi 5 phut")
        self.assertIn("while time.time() < _han:", doan)
        # user bam lenh KHAC thi bo lenh cu, khong giu cho
        self.assertIn('st.get("cmd_gen", 0) != cmd_gen_handled', doan)

    def test_kenh_day_hoac_khong_ton_tai_thi_BO_SOM(self):
        """result 2/4: thu lai cung the -> de vong sync kenh chon kenh khac cho CA PARTY."""
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 3600]
        self.assertIn("if _res in (2, 4):", doan)
        self.assertIn("de sync kenh chon", doan)

    def test_ra_safe_goi_TRUOC_switch_channel(self):
        s = _src()
        i = s.find('if kind == "channel":')
        doan = s[i:i + 2600]
        self.assertLess(doan.find("_ra_safe_truoc_khi_doi_kenh"), doan.find("c.switch_channel("),
                        "phai ra safe TRUOC khi doi kenh")

    def test_BOSS_QD_danh_TAI_BAI_khong_ve_thanh(self):
        """User 27/08: "ve thanh lam cai lon gi vay, danh boss QD o safe point thoi chu".

        do_legion_boss() KHONG teleport (khac boss the gioi): chi gui 0x27 7700 + 0x14 08000100
        de vao INSTANCE boss - dung duoc tu bat ky dau. Reform ve thanh la thua ca mot vong route,
        va bi luat "da o bai train thi xu ly tai cho" nuot -> doi mai khong bao gio danh.
        """
        s = _src()
        i = s.find("boss QD den luot")
        self.assertGreater(i, 0)
        doan = s[max(0, i - 1500):i + 1800]
        self.assertIn("c.do_legion_boss()", doan, "phai danh ngay tai cho")
        self.assertIn("c.navigate_to(", doan, "ra safe truoc khi danh")
        self.assertIn("c.leave_party()", doan, "boss QD la instance SOLO -> roi party truoc")
        # KHONG duoc bump reform de ve thanh nua
        self.assertNotIn("_bump_reform(st)", doan)

    def test_MAT_PARTY_giua_chung_thi_GOM_LAI(self):
        """Pha train = GOM DU PARTY roi RA TRAIN (user 27/08: "phai gom du pt roi ra train chu").

        Party tan giua chung thi phai TIM MOI CACH GOM: moi lai lien tuc, thieu qua lau thi
        reform/sync kenh. Trong luc gom KHONG danh le - leader dung san o diem quai nen quai cu
        vao, no danh MOT MINH (log 27/08 14:36:09-14:37:57).
        """
        s = _src()
        i = s.find("MAT PARTY GIUA CHUNG")
        self.assertGreater(i, 0)
        doan = s[i:i + 2200]
        self.assertIn("_invite_party_participants(c, train_on_map, gap=1.0)", doan, "phai moi lai")
        self.assertIn("_bump_reform(st", doan, "moi mai khong duoc thi gom bang reform")
        self.assertIn("c.flee_mode = True", doan, "khong danh le trong luc gom")
        self.assertIn("_thieu_since", doan)
        # KHONG duoc "rut ve safe roi ha co train" - gom la viec chinh, khong phai di dau ca
        self.assertNotIn("training_started = False", doan)
        self.assertNotIn("c.navigate_to(", doan)

    def test_DU_PARTY_moi_ra_train(self):
        """Truoc day `nj >= 1` -> chi can MOT member la leader keo ra spot danh, du party con
        thieu 3 nguoi."""
        s = _src()
        self.assertIn('if nj >= st["n_members"] and not training_started:', s)
        self.assertNotIn("if nj >= 1 and not training_started:", s)

    def test_thieu_nguoi_THOANG_QUA_thi_khong_ha_train(self):
        """Party lap lai binh thuong chi mat vai giay - ha ngay se thanh nhay ra/nhay vao spot."""
        s = _src()
        i = s.find("MAT PARTY GIUA CHUNG")
        doan = s[i:i + 2200]
        self.assertIn("time.time() - _thieu_since > 20", doan)

    def test_du_party_thi_RESET_moc_thieu(self):
        s = _src()
        i = s.find("MAT PARTY GIUA CHUNG")
        doan = s[i:i + 2200]
        self.assertIn('joined_member_count(pidx) >= st["n_members"]', doan)
        self.assertIn("_thieu_since = 0.0", doan)

    def test_van_ve_thanh_khi_dang_gom_nhau_o_thanh(self):
        """reform_arrived co entry = co nguoi DANG DUNG CHO o thanh -> ve gop that, khong bo roi ho."""
        s = _src()
        i = s.find("_gather_wait_me = bool(_gather)")
        doan = s[i:i + 1600]
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
