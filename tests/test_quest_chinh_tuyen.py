# -*- coding: utf-8 -*-
"""Mode quest chuoi CHINH TUYEN - nac A CHI DOC (documents/QUEST_CHINH_TUYEN.md, user chot 08/10).

  - "Chinh tuyen" hien trong danh sach chuoi (GUI/APK doc chung quests.json), phu tuyen CHUA hien
  - bo chay CS1 (`chuoi`) khong bao gio thay muc chinh tuyen (lo routing sot thi dung yen, khong
    hieu nham "xong het -> thoat game")
  - ke hoach doc DUNG dieu kien server (Eve.emg) tren co/buoc/cap cua acc
  - nac A khong gui goi nao
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R
from bot import quest_runner as Q
from bot.client import GameClient, _load_mark_bitids


class FakeClient:
    mark_flag_get = GameClient.mark_flag_get

    def __init__(self, xong_mids=(), steps=None, cap=120, loaded=True):
        self._label = "fake"
        self._mark_flags_loaded = loaded
        self.mark_flags = {999: 0} if loaded else {}
        bits = _load_mark_bitids()
        for mid in xong_mids:
            i = int(bits[int(mid)]) - 1
            self.mark_flags[i // 8 + 1] = self.mark_flags.get(i // 8 + 1, 0) | (1 << (i % 8))
        self.mission_steps = dict(steps or {})
        self.char_level = cap
        self.char_turn3_element = None
        self.goi = []

    def send(self, *a, **k):
        self.goi.append(a)


class TestChuoiChinhTuyen(unittest.TestCase):
    def test_hien_chinh_tuyen_chua_hien_phu_tuyen(self):
        ds = dict(Q.danh_sach_chuoi())
        self.assertEqual(ds.get("chinh_tuyen"), "Chính tuyến")
        self.assertNotIn("phu_tuyen", ds)
        self.assertIn("cs1_cu_thu", ds)

    def test_cs1_khong_thay_chinh_tuyen(self):
        self.assertIsNone(Q.chuoi("chinh_tuyen"))
        self.assertTrue(Q.la_chinh_tuyen("chinh_tuyen"))
        self.assertFalse(Q.la_chinh_tuyen("cs1_cu_thu"))
        self.assertIsNotNone(Q.chuoi("cs1_cu_thu"))

    def test_co_data(self):
        self.assertGreater(len(Q.quest_chinh_tuyen("chinh_tuyen")), 300)


class TestDieuKienServer(unittest.TestCase):
    # NPC 1 Thon Vong Binh 19011 nhan 10384: cap > 19, co 10401 xong, chua nhan 10384, chua xong 10385
    DK = [[7, 0, 1, 2, 19], [2, 10401, 3, 5, 1], [2, 10384, 2, 0, 0], [2, 10385, 3, 5, 0]]

    def test_du_dieu_kien(self):
        self.assertIs(Q.danh_gia_dk(FakeClient(xong_mids=[10401], cap=20), self.DK), True)

    def test_thieu_cap(self):
        self.assertIs(Q.danh_gia_dk(FakeClient(xong_mids=[10401], cap=19), self.DK), False)

    def test_chua_xong_quest_truoc(self):
        self.assertIs(Q.danh_gia_dk(FakeClient(cap=50), self.DK), False)

    def test_dang_lam_roi(self):
        c = FakeClient(xong_mids=[10401], cap=50, steps={10384: 1})
        self.assertIs(Q.danh_gia_dk(c, self.DK), False)

    def test_da_xong_roi(self):
        c = FakeClient(xong_mids=[10401, 10385], cap=50)
        self.assertIs(Q.danh_gia_dk(c, self.DK), False)

    def test_dieu_kien_chua_doc_duoc_la_chua_biet(self):
        # cls1 (nghi so item) bot chua doc -> None, KHONG doan la dung
        self.assertIsNone(Q.danh_gia_dk(FakeClient(cap=50), [[1, 37741, 1, 2, 0]]))

    def test_cap_turn3_tru_200(self):
        c = FakeClient(cap=230)
        c.char_turn3_element = 7
        self.assertEqual(Q._cap_server(c), 30)


class TestKeHoach(unittest.TestCase):
    def test_chua_nhan_co_la_chua_biet(self):
        self.assertIsNone(Q.ke_hoach_chinh_tuyen(FakeClient(loaded=False), "chinh_tuyen"))

    def test_quest_dang_lam_dung_truoc_va_dung_buoc_server(self):
        # 10384 la quest Cu Thu (khong con trong ke hoach) -> dung Dao Vien (log p52 09/10)
        c = FakeClient(steps={10001: 1}, cap=127)
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")
        q, b, d = kh["se_lam"][0]
        self.assertEqual((q["id"], b), (10001, 1))
        self.assertEqual((d["scene"], d["kieu"], d["idx"]), (12002, "npc", 3))
        self.assertLessEqual(len(kh["se_lam"]), 10)

    def test_quest_da_xong_khong_lam(self):
        c = FakeClient(xong_mids=[10002], steps={10001: 2}, cap=150)
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")
        self.assertNotIn(10001, [q["id"] for q, _b, _d in kh["se_lam"]])

    def test_nhan_duoc_khi_du_dieu_kien(self):
        c = FakeClient(xong_mids=[10401], cap=150)
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")
        self.assertIn(10268, [q["id"] for q, _u in kh["nhan"]])
        self.assertNotIn(10384, [q["id"] for q, _u in kh["nhan"]])     # Cu Thu: mode rieng

    def test_huong_dan_loai_2_khong_phai_chinh_tuyen(self):
        # Trong game: loai 1 [Chinh], 2 [Huong Dan], 3 [Phu] (TextData 20149/50/51). User 08/10:
        # "giup luu yen la quest khac" -> 12296 / 12292 (loai 2) khong vao ke hoach chinh tuyen
        c = FakeClient(cap=139, steps={12292: 2, 12296: 1, 10143: 1, 10001: 1, 12207: 5})
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")
        self.assertEqual([(q["id"], b) for q, b in kh["dang"]], [(10001, 1)])
        # user 09/10: Huong Dan lam SAU Chinh (khong phai quest Chinh)
        self.assertEqual([(q["id"], b) for q, b, _d in kh["se_lam"]], [(10001, 1), (12292, 2),
                                                                      (12296, 1)])
        self.assertIn("12296", Q.quest_chinh_tuyen("huong_dan"))
        self.assertNotIn("12296", Q.quest_chinh_tuyen("chinh_tuyen"))

    def test_cach_a_chi_lam_quest_trong_so(self):
        # user 08/10 "tam thoi lam a": khong tu di nhan quest so khong co (10268 nhan duoc ngay)
        c = FakeClient(xong_mids=[10401], cap=150, steps={10001: 1})
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")
        self.assertIn(10268, [q["id"] for q, _u in kh["nhan"]])
        self.assertEqual([q["id"] for q, _b, _d in kh["se_lam"]], [10001])
        kh_b = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen", toi_da=1000, chi_so=False)
        self.assertIn(10268, [q["id"] for q, _b, _d in kh_b["se_lam"]])

    def test_nac_a_khong_gui_goi(self):
        c = FakeClient(steps={10001: 2}, cap=150)
        log = mock.Mock()
        self.assertTrue(Q.chay_chinh_tuyen_doc(c, "chinh_tuyen", log=log, cho=0))
        self.assertEqual(c.goi, [])
        self.assertTrue(any("QUEST CT" in str(x) for x in log.info.call_args_list))

    def test_log_mot_lan_khi_ke_hoach_khong_doi(self):
        c = FakeClient(steps={10001: 2}, cap=150)
        log = mock.Mock()
        Q.chay_chinh_tuyen_doc(c, "chinh_tuyen", log=log, cho=0)
        n = log.info.call_count
        Q.chay_chinh_tuyen_doc(c, "chinh_tuyen", log=log, cho=0)
        self.assertEqual(log.info.call_count, n)


def _acc(u, song=True, danh=False, ban=False, viec=None):
    return SimpleNamespace(username=u, song=song, dang_danh=danh, lenh_tay_da_lam=0,
                           dang_ban=ban, viec_dang_lam=viec)


class TestQuyetDinh(unittest.TestCase):
    def setUp(self):
        R._pstate(9).pop("qct_da_tat", None)

    def test_moi_acc_song_tu_lam_khong_lap_party(self):
        anh = SimpleNamespace(accs=[_acc("a"), _acc("b", danh=True), _acc("c", song=False)],
                              lenh_tay_gen=0)
        with mock.patch.dict(R.account_clients, {}, clear=True):
            kq = R._chinh_tuyen_quyet(9, anh, {"a": "lap_party", "b": "train", "c": "nghi"})
        self.assertEqual(kq, {"a": "quest", "b": "nghi", "c": "nghi"})

    def test_dang_lam_quest_dinh_tran_giu_quest(self):
        # boss quest / quai doc duong: doi sang `nghi` = huy su kien giua chung (log party 7, 04/10)
        anh = SimpleNamespace(accs=[_acc("a", danh=True, ban=True, viec="quest")], lenh_tay_gen=0)
        with mock.patch.dict(R.account_clients, {}, clear=True):
            self.assertEqual(R._chinh_tuyen_quyet(9, anh, {"a": "nghi"}), {"a": "quest"})

    def test_lenh_tay_duoc_giu(self):
        anh = SimpleNamespace(accs=[_acc("a")], lenh_tay_gen=1)
        with mock.patch.dict(R.account_clients, {}, clear=True):
            self.assertEqual(R._chinh_tuyen_quyet(9, anh, {"a": "nghi"}), {"a": "lenh_tay"})

    def test_lenh_tay_acc_khac_khong_huy_su_kien_dang_do(self):
        # Log p52 09/10 11:27:19: qv810 relogin -> lenh_tay -> qv809/qv811 dang danh Doc Buu bi
        # doi sang `nghi` -> huy su kien giua tran -> server lo moi lan bam NPC
        anh = SimpleNamespace(accs=[_acc("a"), _acc("b", danh=True)], lenh_tay_gen=1)
        anh.accs[1].lenh_tay_da_lam = 1
        dang = SimpleNamespace(_qev={"het": False})
        with mock.patch.dict(R.account_clients, {"b": dang}, clear=True):
            with mock.patch.object(R, "_clients_cua_party", return_value=[("b", dang)]):
                kq = R._quest_cho_viec_dau(9, anh, {"a": "lenh_tay", "b": "nghi"})
        self.assertEqual(kq, {"a": "lenh_tay", "b": "quest"})

    def test_het_quest_thi_tat_game_mot_lan(self):
        anh = SimpleNamespace(accs=[_acc("a")], lenh_tay_gen=0)
        c = SimpleNamespace(_qct_het=True)
        with mock.patch.dict(R.account_clients, {"a": c}, clear=True):
            with mock.patch.object(R, "stop_account") as stop:
                self.assertEqual(R._chinh_tuyen_quyet(9, anh, {"a": "quest"}), {"a": "nghi"})
                R._chinh_tuyen_quyet(9, anh, {"a": "quest"})
        stop.assert_called_once()


def _buoc(mid, n):
    q = Q.quest_chinh_tuyen("chinh_tuyen")[str(mid)]
    return q, n, q["steps"][str(n)]


class TestLyDoKet(unittest.TestCase):
    def test_dao_vien_b3_truong_phi_can_o_vo_tuong(self):
        # user 08/10: "quest nay can slot trong cua pet de NPC" - 10001 B3 Truong Phi, B4 Quan Vu
        q, b, d = _buoc(10001, 3)
        self.assertEqual(d["gia_nhap"], 1)
        self.assertEqual(_buoc(10001, 4)[2]["gia_nhap"], 1)
        c = FakeClient(cap=126, steps={10001: 3})
        c.follow_slots = {1, 2, 3, 4}
        self.assertIn("ô võ tướng", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c.follow_slots = {1, 2, 3}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c.follow_slots = None
        self.assertIn("chưa biết", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_dan_npc_di_theo_khong_chan(self):
        # B5 can Truong Phi + Quan Vu DI THEO (kind 1) - do buoc truoc cho, khong chan
        q, b, d = _buoc(10001, 5)
        self.assertTrue(any(c["kind"] == 1 for c in d["can"]))
        c = FakeClient(cap=126, steps={10001: 5})
        c.follow_slots = {1, 2, 3, 4}
        c.follow_npc = {1: 41041, 2: 12020, 3: 41048, 4: 12043}     # Truong Phi + Quan Vu dang theo
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_npc_dan_bi_mat_thi_can_o_de_lay_lai(self):
        # 10001 B5: su kien "Quan Vu gia nhap lai" (dk cls9 != 12043) -> mat Quan Vu thi phai lay lai
        q, b, d = _buoc(10001, 5)
        c = FakeClient(cap=126, steps={10001: 5})
        c.follow_slots = {1, 2, 3}
        c.follow_npc = {1: 41041, 2: 12020, 3: 41048}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c.follow_slots = {1, 2, 3, 4}
        c.follow_npc = {1: 41041, 2: 12020, 3: 41048, 4: 41050}
        self.assertIn("cần 1 ô võ tướng", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_10023_ngua_co_cho_lay(self):
        # Log p52 09/10: Ma Phu (12001 NPC 6) doi ngua 18005 di theo; ngua = NPC 9 cung map, surface
        # 11 chon 30 ("Bat ve cho han xem thu vay") -> xin gia nhap. User: "noi chuyen voi con ngua".
        q, b, d = _buoc(10023, 1)
        self.assertEqual([(l["npc"], l["scene"], l["kieu"], l["idx"], l["chon_map"].get("11"))
                          for l in d["lay_npc"]], [(18005, 12001, "npc", 9, 30)])
        self.assertIn([7, 5, 2, 0, 0], d["lay_npc"][0]["dk"])     # "doi ngu chua day" (Talk 10563)
        c = FakeClient(cap=126, steps={10023: 1})
        c.follow_slots, c.follow_npc = {1, 3}, {1: 41041, 3: 41048}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c.follow_slots, c.follow_npc = {1, 2, 3, 4}, {1: 1, 2: 2, 3: 3, 4: 4}
        self.assertIn("cần 1 ô võ tướng", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c._qct_khong_tien = ((10023, 1), 3, "npc_khong_theo")
        c.follow_slots, c.follow_npc = {1}, {1: 1}
        self.assertIn("NPC 18005 3 lần", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_quest_co_tran_ngoai_danh_sach_solo_can_party(self):
        q, b, d = _buoc(10384, 2)
        self.assertNotIn(10384, Q.ds_solo("chinh_tuyen"))
        with mock.patch.object(Q, "solo_het", return_value=False):
            self.assertIn("cần party", Q.ly_do_ket(FakeClient(cap=150), "chinh_tuyen", q, b, d))

    def test_solo_het_thi_quest_co_tran_cung_di_le(self):
        # User 09/10: "nhung quest dau nay cu cho solo het, den khi nao t bao di party"
        self.assertTrue(Q.solo_het())
        q, b, d = _buoc(10384, 2)
        self.assertIsNone(Q.ly_do_ket(FakeClient(cap=150), "chinh_tuyen", q, b, d))

    def test_12288_thit_xay_co_cho_lay_thi_khong_chan(self):
        # Client tu dan duong: 12808 NPC 13 = quai Banh Bao Thit chi cham-server (khong bam)
        q, b, d = _buoc(12288, 4)
        u = d["lay_item"][0]
        self.assertEqual((u["item"], u["count"], u["scene"], u["x"], u["y"], u["kieu"], u["idx"],
                          u["bam"], u["tran"]), (26075, 1, 12808, 650, 780, "npc", 13, False, True))
        c = FakeClient(cap=127, steps={12288: 4})
        c.bag_slots = {}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        self.assertIn("không chỉ chỗ lấy", Q.ly_do_ket(c, "chinh_tuyen", q, b, dict(d, lay_item=[])))

    def test_dao_vien_trong_danh_sach_solo(self):
        self.assertIn(10001, Q.ds_solo("chinh_tuyen"))
        q, b, d = _buoc(10001, 1)
        self.assertIsNone(Q.ly_do_ket(FakeClient(cap=126, steps={10001: 1}), "chinh_tuyen", q, b, d))

    def test_thieu_item_thi_dung(self):
        q, b, d = _buoc(10001, 1)
        d = dict(d, can=[{"kind": 3, "id": 29077, "count": 1, "scene": 1}])
        c = FakeClient(cap=126)
        c.bag_slots = {}
        self.assertIn("cần item 29077", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c.bag_slots = {5: [29077, 1]}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_3_lan_khong_len_buoc_thi_dung(self):
        q, b, d = _buoc(10001, 1)
        c = FakeClient(cap=126)
        c._qct_khong_tien = ((10001, 1), 3, "xong")
        self.assertIn("3 lần", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c._qct_khong_tien = ((10001, 1), 3, "im_lang")
        self.assertIn("không phản hồi", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))


class ClientDiLe(FakeClient):
    """Client gia cho lam_buoc_ct: di toi dau cung toi, hoi thoai xong thi server cong buoc."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.running = True
        self.current_map = 1
        self.party_members = []
        self.party_leader = None
        self.flee_mode = True
        self.viec = []
        self.len_buoc = True

    def _wait_combat_clear(self, idle=1.0, cap=120.0):
        return True

    def leave_party(self):
        self.viec.append("roi_party")
        self.party_members, self.party_leader = [], None

    def follow_smart_route(self, dest, safe, abort=None, flee=True):
        self.viec.append(("route", dest, safe, flee))
        self.current_map = dest
        return True

    def navigate_to(self, x, y, abort=None, flee=True):
        self.viec.append(("nav", x, y, flee))
        return True

    def quest_kich_hoat(self, kieu, idx):
        self.viec.append(("kich_hoat", kieu, idx, self.flee_mode))

    def quest_hoi_thoai(self, chon=(), abort=None, im_lang=60.0, toi_da=600.0):
        self.viec.append(("hoi_thoai", dict(chon)))
        if self.len_buoc:
            mid = next(iter(self.mission_steps))
            self.mission_steps[mid] += 1
        return "xong"

    def claim_achievements(self):
        self.viec.append("thanh_tuu")


class TestLamBuoc(unittest.TestCase):
    def test_roi_party_di_map_tat_flee_roi_moi_bam(self):
        q, b, d = _buoc(10001, 1)
        c = ClientDiLe(cap=126, steps={10001: 1})
        c.party_members = ["x"]
        self.assertTrue(Q.lam_buoc_ct(c, q, b, d))
        self.assertEqual(c.viec[0], "roi_party")
        self.assertEqual(c.viec[1], ("route", d["scene"], (d["x"], d["y"]), True))   # di le: CHAY
        kh = next(v for v in c.viec if v[0] == "kich_hoat")
        self.assertEqual(kh, ("kich_hoat", "npc", d["idx"], False))   # bam NPC: DA TAT flee
        self.assertEqual(c.mission_steps[10001], 2)

    def test_khong_len_buoc_dem_lan(self):
        q, b, d = _buoc(10001, 1)
        c = ClientDiLe(cap=126, steps={10001: 1})
        c.len_buoc = False
        for _ in range(3):
            self.assertFalse(Q.lam_buoc_ct(c, q, b, d))
        self.assertEqual(c._qct_khong_tien, ((10001, 1), 3, "xong"))
        self.assertIn("3 lần", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_server_im_cung_dem_bi_huy_thi_khong(self):
        # Log p52 09/10: vuchin/vummot `im_lang` thu mai moi 60s vi bo dem chi dem "xong"
        q, b, d = _buoc(10001, 1)
        c = ClientDiLe(cap=126, steps={10001: 1})
        c.len_buoc = False
        c.quest_hoi_thoai = lambda chon=(), abort=None, im_lang=60.0, toi_da=600.0: "im_lang"
        for _ in range(3):
            Q.lam_buoc_ct(c, q, b, d)
        self.assertEqual(c._qct_khong_tien, ((10001, 1), 3, "im_lang"))
        c2 = ClientDiLe(cap=126, steps={10001: 1})
        c2.quest_hoi_thoai = lambda chon=(), abort=None, im_lang=60.0, toi_da=600.0: "dung"
        Q.lam_buoc_ct(c2, q, b, d)
        self.assertIsNone(getattr(c2, "_qct_khong_tien", None))


class ClientNgua(ClientDiLe):
    """10023 B1: noi chuyen ngua (NPC 9) -> ngua theo (o 2); Ma Phu chi len buoc khi ngua dang theo."""

    def __init__(self, *a, ngua_theo=True, **k):
        super().__init__(*a, **k)
        self.follow_slots, self.follow_npc = {1}, {1: 41041}
        self.ngua_theo = ngua_theo
        self._dang = None

    def quest_kich_hoat(self, kieu, idx):
        self._dang = idx
        super().quest_kich_hoat(kieu, idx)

    def quest_hoi_thoai(self, chon=(), abort=None, im_lang=60.0, toi_da=600.0):
        self.viec.append(("hoi_thoai", dict(chon)))
        if self._dang == 9:
            if self.ngua_theo and dict(chon).get("11") == 30:
                self.follow_slots.add(2)
                self.follow_npc[2] = 18005
        elif self._dang == 6 and 18005 in self.follow_npc.values():
            self.mission_steps[10023] = 0         # tra quest -> co xong (mark_flag_get duoi)
        return "xong"

    def mark_flag_get(self, bit):
        return self.mission_steps.get(10023) == 0


class TestLayNpc(unittest.TestCase):
    def test_lay_ngua_roi_moi_toi_ma_phu(self):
        q, b, d = _buoc(10023, 1)
        c = ClientNgua(cap=126, steps={10023: 1})
        c.current_map = 12001
        self.assertTrue(Q.lam_buoc_ct(c, q, b, d))
        bam = [v for v in c.viec if v[0] in ("kich_hoat", "nav")]
        self.assertEqual(bam[:2], [("nav", 2250, 1540, True), ("kich_hoat", "npc", 9, False)])
        self.assertEqual(bam[-2:], [("nav", d["x"], d["y"], True), ("kich_hoat", "npc", 6, False)])
        self.assertIn(("hoi_thoai", d["lay_npc"][0]["chon_map"]), c.viec)

    def test_ngua_da_theo_thi_khong_di_lay(self):
        q, b, d = _buoc(10023, 1)
        c = ClientNgua(cap=126, steps={10023: 1})
        c.current_map = 12001
        c.follow_slots, c.follow_npc = {1, 2}, {1: 41041, 2: 18005}
        self.assertTrue(Q.lam_buoc_ct(c, q, b, d))
        self.assertNotIn(("kich_hoat", "npc", 9, False), c.viec)

    def test_ngua_khong_theo_thi_dem_va_khong_bam_ma_phu(self):
        q, b, d = _buoc(10023, 1)
        c = ClientNgua(cap=126, steps={10023: 1}, ngua_theo=False)
        c.current_map = 12001
        import itertools
        with mock.patch.object(Q.time, "sleep"),                 mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            for _ in range(3):
                self.assertFalse(Q.lam_buoc_ct(c, q, b, d))
        self.assertNotIn(("kich_hoat", "npc", 6, False), c.viec)
        self.assertEqual(c._qct_khong_tien, ((10023, 1), 3, "npc_khong_theo"))
        self.assertIn("không đi theo", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))


class TestBoChuoiCuThu(unittest.TestCase):
    """User 09/10: "Thuong khung loan vu la quest 8 cu thu" - quest chuoi CS1 mang nhan [Chinh]
    nhung KHONG duoc lam o mode chinh tuyen (di le), ke ca khi solo_het bat."""

    def test_8_cu_thu_khong_vao_ke_hoach(self):
        cs1 = {int(q["id"]) for q in Q.chuoi("cs1_cu_thu")["quests"]}
        self.assertIn(10806, cs1)
        self.assertTrue(cs1 <= Q.ma_chuoi_rieng())
        c = FakeClient(cap=127, steps={10806: 1, 10528: 2, 12288: 4})
        kh = Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen", toi_da=1000)
        lam = {int(q["id"]) for q, _b, _d in kh["se_lam"]}
        self.assertEqual(lam & cs1, set())
        self.assertIn(12288, lam)
        self.assertEqual({int(q["id"]) for q, _b in kh["rieng"]}, {10806, 10528})
        self.assertFalse({int(q["id"]) for q in kh["xong"]} & cs1)


class ClientItem(ClientDiLe):
    """12288 B4: dung o 12808 bat hop may -> sau vai giay danh quai thi tui co thit xay; Tai Hoa Da
    (12003 NPC 9) chi len buoc khi co thit xay."""

    def __init__(self, *a, ra_sau=3, bam_ra=True, **k):
        super().__init__(*a, **k)
        self.bag_slots = {}
        self.ra_sau, self.bam_ra = ra_sau, bam_ra
        self.hop_may = 0
        self._dang = None

    def combat_ready(self):
        self.viec.append("combat_ready")
        self.hop_may += 1

    def quest_kich_hoat(self, kieu, idx):
        self._dang = (kieu, idx)
        super().quest_kich_hoat(kieu, idx)

    def quest_hoi_thoai(self, chon=(), abort=None, im_lang=60.0, toi_da=600.0):
        self.viec.append(("hoi_thoai", dict(chon)))
        if self._dang == ("npc", 9) and self.bag_slots:
            self.mission_steps[12288] += 1
        elif self._dang == ("npc", 77) and self.bam_ra:
            self.bag_slots = {5: [26075, 1]}
        return "xong"

    def ngu(self, _s):
        if self.hop_may:
            self.ra_sau -= 1
            if self.ra_sau <= 0:
                self.bag_slots = {5: [26075, 1]}


class TestLayItem(unittest.TestCase):
    def _chay(self, c, d, lan=1):
        import itertools
        q = Q.quest_chinh_tuyen("chinh_tuyen")["12288"]
        with mock.patch.object(Q.time, "sleep", side_effect=c.ngu), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            return [Q.lam_buoc_ct(c, q, 4, d) for _ in range(lan)]

    def test_danh_quai_quanh_diem_roi_moi_giao(self):
        q, b, d = _buoc(12288, 4)
        c = ClientItem(cap=127, steps={12288: 4})
        self.assertEqual(self._chay(c, d), [True])
        self.assertEqual(c.viec[0], ("route", 12808, (650, 780), True))
        self.assertEqual(c.hop_may, 1)
        self.assertNotIn(("kich_hoat", "npc", 13, False), c.viec)      # quai cham-server: khong bam
        self.assertEqual(c.viec[-2:], [("kich_hoat", "npc", 9, False), ("hoi_thoai", {})])
        self.assertEqual(c.mission_steps[12288], 5)

    def test_chua_ra_item_thi_danh_tiep_khong_dem_ket(self):
        q, b, d = _buoc(12288, 4)
        c = ClientItem(cap=127, steps={12288: 4}, ra_sau=10 ** 6)
        self.assertEqual(self._chay(c, d, lan=4), [False] * 4)
        self.assertEqual(c.hop_may, 1)                 # cung diem -> khong gui lai chuoi setup
        self.assertIsNone(getattr(c, "_qct_khong_tien", None))
        self.assertNotIn(("kich_hoat", "npc", 9, False), c.viec)

    def test_bam_npc_khong_tran_3_lan_khong_ra_item_thi_chu_y(self):
        q, b, d = _buoc(12288, 4)
        d = dict(d, lay_item=[dict(d["lay_item"][0], kieu="npc", idx=77, bam=True, tran=False)])
        c = ClientItem(cap=127, steps={12288: 4}, bam_ra=False)
        self.assertEqual(self._chay(c, d, lan=3), [False] * 3)
        self.assertEqual(c._qct_khong_tien, ((12288, 4), 3, "item_khong_co"))
        self.assertIn("không nhận được item", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_bam_npc_ra_item(self):
        q, b, d = _buoc(12288, 4)
        d = dict(d, lay_item=[dict(d["lay_item"][0], kieu="npc", idx=77, bam=True, tran=False)])
        c = ClientItem(cap=127, steps={12288: 4})
        self.assertEqual(self._chay(c, d), [True])
        self.assertIn(("kich_hoat", "npc", 77, False), c.viec)
        self.assertEqual(c.hop_may, 0)


class ClientMo(ClientDiLe):
    """11116: dao mo 3 map 12591. Moi lan di trong mo thi co 1 tran -> +3 Tich Sa."""

    VK_CU = 0x5000

    def __init__(self, *a, cuoc=2, **k):
        super().__init__(*a, **k)
        self.state = SimpleNamespace(danh_khoang_den=0.0)
        self.equip_by_fit = {3: self.VK_CU}
        self.pet_equip_by_fit = {1: {3: 0x5001}}
        self.active_pet_slot = 1
        self.bag_slots = {10 + i: [10001, 1] for i in range(cuoc)}
        self.di = []

    def _deo(self, bang, slot):
        tid = self.bag_slots[slot][0]
        cu = bang.get(3)
        bang[3] = tid
        if cu:
            self.bag_slots[slot] = [cu, 1]
        else:
            self.bag_slots.pop(slot)

    def equip_item(self, slot):
        self.viec.append(("deo", 0, self.bag_slots[slot][0]))
        self._deo(self.equip_by_fit, slot)

    def equip_pet_item(self, pet, slot):
        self.viec.append(("deo", pet, self.bag_slots[slot][0]))
        self._deo(self.pet_equip_by_fit.setdefault(pet, {}), slot)

    def unequip_item(self, fit, follow=0):
        self.viec.append(("coi", follow, fit))

    def navigate_to(self, x, y, abort=None, flee=True):
        self.di.append((x, y, flee, self.state.danh_khoang_den > 0))
        n = sum(r[1] for r in self.bag_slots.values() if r[0] == 37407)
        self.bag_slots = {k: v for k, v in self.bag_slots.items() if v[0] != 37407}
        self.bag_slots[90] = [37407, n + 3]
        return True


class TestDaoMo(unittest.TestCase):
    """User 10/10: 11116 phai deo cuoc danh quai khoang, ko bo chay; chon mo theo quest."""

    def test_data_chon_mo_theo_diem_quest(self):
        q, b, d = _buoc(11116, 1)
        u = d["lay_item"][0]
        self.assertEqual((u["item"], u["count"], u["scene"]), (37407, 15, 12591))
        # diem quest (1250,1030) nam GIUA mo 2 (y 200-560) va mo 3 (y 1480-1860): mo 3 gan hon
        self.assertEqual((u["mo"]["id"], u["mo"]["x0"], u["mo"]["y0"], u["mo"]["x1"], u["mo"]["y1"]),
                         (3, 960, 1480, 1560, 1860))
        self.assertEqual(u["mo"]["quai"], [25008])          # Khoang Chi lv2
        self.assertTrue(Q._mo_khoang(u))

    def test_khong_co_cuoc_thi_chu_y(self):
        q, b, d = _buoc(11116, 1)
        c = ClientMo(cap=15, steps={11116: 1}, cuoc=0)
        self.assertIn("cần Cuốc", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c = ClientMo(cap=15, steps={11116: 1})
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_deo_cuoc_di_trong_mo_khong_chay_roi_tra_vu_khi(self):
        q, b, d = _buoc(11116, 1)
        c = ClientMo(cap=15, steps={11116: 1})
        import itertools
        with mock.patch.object(Q.time, "sleep"), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            ok = Q.lam_buoc_ct(c, q, b, d)
        self.assertTrue(ok)
        self.assertEqual(c.viec[1:3], [("deo", 0, 10001), ("deo", 1, 10001)])   # char + pet
        mo = d["lay_item"][0]["mo"]
        self.assertEqual(len(c.di), 5)                     # 5 vong x 3 = 15 Tich Sa
        for x, y, flee, danh in c.di:
            self.assertTrue(mo["x0"] <= x <= mo["x1"] and mo["y0"] <= y <= mo["y1"])
            self.assertFalse(flee)
            self.assertTrue(danh)                          # co "danh khoang" bat khi di trong mo
        self.assertEqual(c.equip_by_fit[3], ClientMo.VK_CU)          # tra lai vu khi cu
        self.assertEqual(c.pet_equip_by_fit[1][3], 0x5001)
        self.assertIsNone(c._qct_vk_cu)
        self.assertEqual(c.state.danh_khoang_den, 0.0)
        self.assertEqual(c.viec[-2:], [("kich_hoat", "npc", 1, False), ("hoi_thoai", {})])

    def test_combat_khong_chay_khoang_khi_dang_dao_mo(self):
        import time as _t
        from bot import combat
        st = SimpleNamespace(mineral_battle=True, enemy_names=set(), danh_khoang_den=0.0)
        self.assertTrue(combat._chay_quai_khoang(st))
        st.danh_khoang_den = _t.time() + 60
        self.assertFalse(combat._chay_quai_khoang(st))
        st.danh_khoang_den = _t.time() - 1               # het han -> quay ve bo chay
        self.assertTrue(combat._chay_quai_khoang(st))
        self.assertFalse(combat._chay_quai_khoang(SimpleNamespace(mineral_battle=False,
                                                                  enemy_names=set())))


class ClientHop(ClientDiLe):
    """11120: tui 35 Tich Sa. Lan hop dau THAT BAI (mat 2 Sa), lan sau ra 1 Tich Thach."""

    def __init__(self, *a, sa=35, **k):
        super().__init__(*a, **k)
        self.bag_slots = {5: [37407, sa]} if sa else {}
        self.hop = []

    def combine_slots(self, o1, o2):
        self.hop.append((o1, o2))
        self.bag_slots[o1] = [37407, self.bag_slots[o1][1] - 2]
        if len(self.hop) >= 2:
            self.bag_slots[7] = [44042, 1]


class TestHopTichThach(unittest.TestCase):
    """User 10/10 xac nhan: 2 Tich Sa -> 1 Tich Thach (11120), hop co the that bai."""

    def test_hop_toi_khi_ra_roi_giao(self):
        q, b, d = _buoc(11120, 1)
        self.assertEqual(Q._HOP[d["lay_item"][0]["item"]], 37407)
        c = ClientHop(cap=16, steps={11120: 1})
        import itertools
        with mock.patch.object(Q.time, "sleep"), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            self.assertTrue(Q.lam_buoc_ct(c, q, b, d))
        self.assertEqual(c.hop, [(5, 5), (5, 5)])          # hop chinh stack do (cung o)
        self.assertFalse(any(v[0] == "route" and v[1] == 12591 for v in c.viec
                             if isinstance(v, tuple)))       # KHONG chay di dao mo
        self.assertEqual(c.viec[-2:], [("kich_hoat", "npc", 1, False), ("hoi_thoai", {})])

    def test_du_nguyen_lieu_thi_khong_doi_cuoc(self):
        q, b, d = _buoc(11120, 1)
        c = ClientHop(cap=16, steps={11120: 1})
        c.equip_by_fit = {3: 0x5000}
        self.assertIsNone(Q.ly_do_ket(c, "chinh_tuyen", q, b, d))
        c = ClientHop(cap=16, steps={11120: 1}, sa=1)       # het Sa -> phai dao mo -> can cuoc
        c.equip_by_fit = {3: 0x5000}
        self.assertIn("cần Cuốc", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))

    def test_hai_o_khac_nhau(self):
        c = SimpleNamespace(bag_slots={3: [37407, 1], 9: [37407, 1], 4: [1, 5]})
        self.assertEqual(Q._o_nguyen_lieu(c, 37407), (3, 9))
        c.bag_slots = {3: [37407, 1]}
        self.assertIsNone(Q._o_nguyen_lieu(c, 37407))


class TestKhongDonateKhiLamQuest(unittest.TestCase):
    def test_mode_quest_chinh_tuyen_khong_donate(self):
        # User 10/10: "che do lam nhiem vu nay thi ko donate nguyen lieu cho quan doan"
        self.assertFalse(R._cho_donate_nguyen_lieu({"mode": "quest", "quest_key": "chinh_tuyen",
                                                    "auto_donate_materials": True}))
        self.assertTrue(R._cho_donate_nguyen_lieu({"mode": "quest", "quest_key": "cs1_cu_thu"}))
        self.assertTrue(R._cho_donate_nguyen_lieu({"mode": "train"}))
        self.assertFalse(R._cho_donate_nguyen_lieu({"mode": "train",
                                                    "auto_donate_materials": False}))


class TestChayChinhTuyen(unittest.TestCase):
    def test_so_khong_co_quest_chinh_thi_het(self):
        c = ClientDiLe(cap=139, steps={10143: 1, 10600: 1})     # chi co [Phu]
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertTrue(c._qct_het)
        self.assertNotIn("kich_hoat", [v[0] for v in c.viec if isinstance(v, tuple)])

    def test_chi_co_huong_dan_thi_lam_huong_dan(self):
        # user 09/10: het [Chinh] thi lam [Huong Dan] (truoc day: tat game)
        c = ClientDiLe(cap=139, steps={12292: 2, 12296: 1})
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertFalse(getattr(c, "_qct_het", False))
        self.assertIn("kich_hoat", [v[0] for v in c.viec if isinstance(v, tuple)])

    def test_ket_thi_dung_yen_va_len_chu_y(self):
        c = ClientDiLe(cap=126, steps={10001: 3})
        c.follow_slots = {1, 2, 3, 4}
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertFalse(getattr(c, "_qct_het", False))
        self.assertEqual([k["id"] for k in c._qct_chu_y], [10001])
        self.assertEqual(c.viec, [])

    def test_lam_mot_buoc(self):
        c = ClientDiLe(cap=126, steps={10001: 1})
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertEqual(c.mission_steps[10001], 2)
        self.assertEqual(c._qct_chu_y, [])

    def test_khong_gioi_han_so_quest_moi_phien(self):
        # user 09/10: "gioi han lam gi, ko can thiet"
        c = ClientDiLe(cap=126, steps={10001: 1})
        c._qct_da_xong = set(range(50))
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertFalse(getattr(c, "_qct_het", False))
        self.assertEqual(c.mission_steps[10001], 2)


class TestHuongDanSauChinh(unittest.TestCase):
    """User 09/10: lam [Chinh] truoc, het thi lam [Huong Dan], [Chinh] xuat hien lai thi quay ve."""

    def _lam(self, steps, cap=127):
        c = FakeClient(cap=cap, steps=steps)
        return [int(q["id"]) for q, _b, _d in Q.ke_hoach_chinh_tuyen(c, "chinh_tuyen")["se_lam"]]

    def test_het_chinh_thi_lam_huong_dan(self):
        # So p52 16:33 vummot: chi con Cu Thu 10806 + Phu + 12290 Huong Dan
        self.assertEqual(self._lam({10806: 1, 10818: 1, 12290: 1, 12207: 5}), [12290])

    def test_co_chinh_thi_chinh_truoc(self):
        self.assertEqual(self._lam({12290: 5, 10015: 1, 12292: 2}), [10015, 12290, 12292])

    def test_12290_b5_giao_10015(self):
        # Cuu Soi (12179 NPC 1) chon 30: giao 10015 [Chinh] + tam xoa 12290 -> quest Chinh len dau
        d = Q.quest_chinh_tuyen("huong_dan")["12290"]["steps"]["5"]
        self.assertEqual((d["scene"], d["kieu"], d["idx"], d["chon"]), (12179, "npc", 1, [30]))
        self.assertEqual(self._lam({10015: 1}), [10015])

    def test_het_ca_hai_thi_tat_game(self):
        c = ClientDiLe(cap=127, steps={10806: 1, 10818: 1})
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertTrue(c._qct_het)

    def test_lam_buoc_huong_dan(self):
        c = ClientDiLe(cap=127, steps={12290: 2})
        Q.chay_chinh_tuyen(c, "chinh_tuyen", cho=0)
        self.assertEqual(c.mission_steps[12290], 3)
        self.assertIn(("kich_hoat", "npc", 1, False), c.viec)


class TestChuY(unittest.TestCase):
    def test_dong_chu_y_va_bo_qua(self):
        c = SimpleNamespace(_qct_chu_y=[{"id": 10001, "ten": "Đào Viên Kết Nghĩa", "buoc": "3/7",
                                         "ly_do": "can 1 o vo tuong"}])
        R.quest_ket_notify_dismissed.clear()
        with mock.patch.dict(R.account_clients, {"a": c}, clear=True):
            with mock.patch.object(R, "party_accounts", return_value=[("a", "p")]):
                rows = R.quest_ket_notify_items(0)
                self.assertEqual(rows[0]["kind"], "quest_ket")
                self.assertEqual(rows[0]["id"], "10001")
                R.quest_ket_notify_skip("a", "10001", "3/7")
                self.assertEqual(R.quest_ket_notify_items(0), [])


class TestOVoTuong(unittest.TestCase):
    """S:015-001 them / S:015-002 xoa vo tuong cua CHINH MINH -> follow_slots."""

    def _goi(self, sub, ent, idx):
        import struct
        body = bytes([sub, 0]) + ent + bytes([idx]) + bytes(6)
        return bytes([0xC0, 0x91]) + struct.pack("<H", 7 + len(body)) + bytes([0, 0, 0x0F]) + body

    def test_them_xoa(self):
        from bot import client as client_module
        g = client_module.GameClient("user", "token")
        g.self_entity = bytes([0x11]) * 8
        g.follow_slots = {1, 2}
        g._dispatch(0x0F, self._goi(1, g.self_entity, 3))
        self.assertEqual(g.follow_slots, {1, 2, 3})
        g._dispatch(0x0F, self._goi(2, g.self_entity, 1))
        self.assertEqual(g.follow_slots, {2, 3})
        g._dispatch(0x0F, self._goi(1, bytes([0x22]) * 8, 4))      # nguoi khac -> khong tinh
        self.assertEqual(g.follow_slots, {2, 3})

    def test_nho_npc_tung_o(self):
        # S:015-001 +跟隨索引(1) +NPCID(4): ngua 18005 vao o 2
        import struct
        from bot import client as client_module
        g = client_module.GameClient("user", "token")
        g.self_entity = bytes([0x11]) * 8
        g.follow_slots, g.follow_npc = {1}, {1: 41041}
        body = bytes([1, 0]) + g.self_entity + bytes([2]) + struct.pack("<I", 18005) + bytes(2)
        g._dispatch(0x0F, bytes([0xC0, 0x91]) + struct.pack("<H", 7 + len(body))
                    + bytes([0, 0, 0x0F]) + body)
        self.assertEqual(g.follow_npc, {1: 41041, 2: 18005})
        self.assertTrue(Q._dang_theo(g, 18005))
        g._dispatch(0x0F, self._goi(2, g.self_entity, 2))
        self.assertEqual(g.follow_npc, {1: 41041})
        self.assertIs(Q._dang_theo(g, 18005), False)


class TestChonTheoSurfacePhatLaiCapture(unittest.TestCase):
    """Bot tra loi CHON theo surface server hoi (`chon_map` sinh tu Eve.emg) phai gui DUNG TUNG GOI
    nhu client that trong capture (sai ma = server ngat ket noi)."""

    def _phat(self, fn, trigger, lan, kieu, idx, chon):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import test_quest_hoi_thoai_capture as T
        fr = T._frames(os.path.join(T.CAP, fn))
        vt = [n for n, (k, op, b) in enumerate(fr) if k == "C" and op == 0x14 and b == trigger]
        return T.TestPhatLaiCapture()._chay_tu(fr, vt[lan], kieu, idx, chon=chon)

    def test_10806_b1_npc_hai_su_kien(self):
        bang = Q.quest_chinh_tuyen("chinh_tuyen")["10806"]["steps"]["1"]["chon_map"]
        kq, gui, that = self._phat("cs1_10806_khungthuong_20261003.pcap", b"\x01\x00\x01\x00", 1,
                                   "npc", 1, bang)
        self.assertEqual((kq, gui), ("xong", that))
        self.assertIn(b"\x09\x00\x1e", gui)

    def test_10528_b1_chon_theo_surface(self):
        bang = Q.quest_chinh_tuyen("chinh_tuyen")["10528"]["steps"]["1"]["chon_map"]
        kq, gui, that = self._phat("cs1_10528_thaiho_20261003.pcap", b"\x01\x00\x04\x00", 1,
                                   "npc", 4, bang)
        self.assertEqual((kq, gui), ("xong", that))

    def test_surface_khong_co_trong_bang_thi_dung(self):
        kq, gui, _that = self._phat("cs1_10806_khungthuong_20261003.pcap", b"\x01\x00\x01\x00", 1,
                                    "npc", 1, {"99": 30})
        self.assertEqual(kq, "can_chon")
        self.assertFalse(any(b[:2] == b"\x09\x00" for b in gui))


def _buoc_hd(mid, n):
    q = Q.quest_chinh_tuyen("huong_dan")[str(mid)]
    return q, n, q["steps"][str(n)]


class ClientDiLai(ClientDiLe):
    """11176 map 12582: KHONG co quai lao vao -> phai di moi gap tran; moi 3 lan di ra 2 item."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.bag_slots = {}
        self.di = []

    def combat_ready(self):
        self.viec.append("combat_ready")

    def navigate_to(self, x, y, abort=None, flee=True):
        self.di.append((x, y, flee))
        if len(self.di) % 3 == 0:
            n = sum(r[1] for r in self.bag_slots.values() if r[0] == 27003)
            self.bag_slots = {7: [27003, n + 2]}
        return True


class TestDiLaiKhiKhongCoQuaiLaoVao(unittest.TestCase):
    """Log p52 10/10: vubon dung o 12582 (1300,1000) 21 phut 0 tran; Vuba di tren cung map 6s gap
    tran. Data: quanh diem khong co NPC quai serStroke (12841/12801 thi co -> dung yen van ra tran)."""

    def test_data_danh_dau_di_lai_dung_cho(self):
        u = _buoc(11176, 1)[2]["lay_item"][0]
        self.assertEqual((u["item"], u["scene"]), (27003, 12582))
        self.assertTrue(u.get("di_lai"))
        for mid, b in ((11172, 1), (11168, 1), (11164, 2)):     # farm duoc khi dung yen
            for u in _buoc(mid, b)[2]["lay_item"]:
                self.assertFalse(u.get("di_lai"), (mid, u["scene"]))
        self.assertFalse(_buoc(12288, 4)[2]["lay_item"][0].get("di_lai"))   # Banh Bao Thit

    def test_di_lai_quanh_diem_khong_bo_chay_roi_giao(self):
        q, b, d = _buoc(11176, 1)
        c = ClientDiLai(cap=136, steps={11176: 1})
        import itertools
        with mock.patch.object(Q.time, "sleep"), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            self.assertTrue(Q.lam_buoc_ct(c, q, b, d))
        self.assertEqual(len(c.di), 9)                      # 3 nhip x 2 item = 6
        u = d["lay_item"][0]
        for x, y, flee in c.di:
            self.assertFalse(flee)
            self.assertLessEqual(abs(x - u["x"]) + abs(y - u["y"]), Q._DI_LAI_PX)
        self.assertGreater(len({(x, y) for x, y, _f in c.di}), 1)
        self.assertEqual(c.viec[-2:], [("kich_hoat", "npc", d["idx"], False), ("hoi_thoai", {})])


class TestKhongBoChayTaiDiemFarm(unittest.TestCase):
    """Log p52 10/10 Vuba 11180 map 12861 (770,1610): moi ~75s `lam_buoc_ct` lap lai -> `_di_toi`
    (flee=True) toi CHINH diem dang dung -> 12/69 tran bi BO CHAY. Dang o diem thi khong goi lai."""

    U = {"item": 34004, "count": 1, "scene": 12861, "x": 770, "y": 1610, "kieu": None, "idx": 0,
         "chon_map": {}, "tran": False, "bam": False}

    def _chay(self, pos, **them):
        c = ClientDiLai(cap=136, steps={11180: 1})
        c.current_map, c.pos = 12861, pos
        u = dict(self.U, **them)
        import itertools
        with mock.patch.object(Q.time, "sleep"), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 5.0)):
            Q._lay_item(c, "sig", u, None, None)
        return c

    def test_dang_o_diem_KHONG_di_toi_bo_chay(self):
        c = self._chay((780, 1600))
        self.assertEqual([d for d in c.di if d[2]], [], "di toi diem dang dung kem flee -> mat tran")
        self.assertFalse(c.flee_mode)

    def test_xa_diem_van_di_toi_va_bo_chay_doc_duong(self):
        c = self._chay((200, 300))
        self.assertEqual(c.di[0], (770, 1610, True))

    def test_khac_map_hoac_chua_biet_vi_tri_van_di(self):
        self.assertFalse(Q._dang_o_diem_farm(type("C", (), {"current_map": 1, "pos": (770, 1610)})(),
                                              self.U))
        self.assertFalse(Q._dang_o_diem_farm(type("C", (), {"current_map": 12861, "pos": None})(),
                                              self.U))

    def test_chi_ap_cho_diem_danh_quai(self):
        """NPC bam / mo dao giu duong cu (bam can toi sat NPC, dao mo co vong rieng)."""
        c = type("C", (), {"current_map": 12861, "pos": (770, 1610)})()
        self.assertTrue(Q._dang_o_diem_farm(c, self.U))
        self.assertFalse(Q._dang_o_diem_farm(c, dict(self.U, bam=True)))
        self.assertFalse(Q._dang_o_diem_farm(c, dict(self.U, mo={"x": 1})))


class ClientTro(ClientDiLe):
    """12290 B7: Cuu Soi (14096) o di theo 2; chu nha tro (12244 NPC 3) chon "Võ Tướng" -> gui vao;
    Ly Chau (NPC 2) chi len buoc khi Cuu Soi KHONG con di theo."""

    def __init__(self, *a, gui_duoc=True, **k):
        super().__init__(*a, **k)
        self.follow_slots, self.follow_npc = {1, 2}, {1: 41041, 2: 14096}
        self.vantieu_roster_ids = {}
        self.gui_duoc = gui_duoc
        self._dang = None

    def quest_kich_hoat(self, kieu, idx):
        self._dang = (kieu, idx)
        super().quest_kich_hoat(kieu, idx)

    def quest_hoi_thoai(self, chon=(), abort=None, im_lang=60.0, toi_da=600.0, nha_tro=None):
        self.viec.append(("hoi_thoai", dict(chon), nha_tro))
        if self._dang == ("npc", 3) and nha_tro == 2 and self.gui_duoc:
            self.follow_npc.pop(2)
            self.follow_slots.discard(2)
            self.vantieu_roster_ids[1] = 14096
        elif self._dang == ("npc", 2) and 14096 not in self.follow_npc.values():
            self.mission_steps.pop(12290)
            self.mission_steps[12292] = 1
        return "xong"


class TestGuiNhaTro(unittest.TestCase):
    """User 10/10 xac nhan: 12290 B7 "hãy gửi Cửu Sởi vào Nhà Trọ" (thoai 53107)."""

    def test_data_cho_gui(self):
        d = _buoc_hd(12290, 7)[2]
        self.assertEqual(d["cat_tro"], [{"scene": 12244, "kieu": "npc", "idx": 3, "x": 490,
                                         "y": 400, "chon_map": {"2": 32}, "npc": 14096}])
        self.assertIn("GUI NPC 14096 vao nha tro", Q._mo_ta(_buoc_hd(12290, 7)[0], 7, d))

    def _chay(self, c, lan=1):
        q, b, d = _buoc_hd(12290, 7)
        import itertools
        with mock.patch.object(Q.time, "sleep"), \
                mock.patch.object(Q.time, "time", side_effect=itertools.count(0, 1.0)):
            return [Q.lam_buoc_ct(c, q, b, d) for _ in range(lan)]

    def test_gui_cuu_soi_roi_moi_gap_ly_chau(self):
        c = ClientTro(cap=127, steps={12290: 7})
        c.current_map = 12244
        self.assertEqual(self._chay(c), [True])
        bam = [v for v in c.viec if v[0] in ("kich_hoat", "hoi_thoai")]
        self.assertEqual(bam, [("kich_hoat", "npc", 3, False), ("hoi_thoai", {"2": 32}, 2),
                               ("kich_hoat", "npc", 2, False), ("hoi_thoai", {}, None)])
        self.assertNotIn(12290, c.mission_steps)

    def test_da_o_nha_tro_thi_khong_gui_lai(self):
        c = ClientTro(cap=127, steps={12290: 7})
        c.current_map = 12244
        c.follow_npc, c.vantieu_roster_ids = {1: 41041}, {3: 14096}
        self.assertEqual(self._chay(c), [True])
        self.assertNotIn(("kich_hoat", "npc", 3, False), c.viec)

    def test_gui_khong_duoc_3_lan_thi_chu_y(self):
        q, b, d = _buoc_hd(12290, 7)
        c = ClientTro(cap=127, steps={12290: 7}, gui_duoc=False)
        c.current_map = 12244
        self.assertEqual(self._chay(c, lan=3), [False] * 3)
        self.assertNotIn(("kich_hoat", "npc", 2, False), c.viec)
        self.assertEqual(c._qct_khong_tien, ((12290, 7), 3, "nha_tro"))
        self.assertIn("nhà trọ", Q.ly_do_ket(c, "chinh_tuyen", q, b, d))


class TestClientGuiNhaTro(unittest.TestCase):
    """quest_hoi_thoai(nha_tro=o): chon 32 -> server mo bang (S:031-007) -> C:031-003 o -> S:031-003
    -> C:031-010 dong bang -> 0x14 06 buoc tiep (client: OnClose SetConduct(true)) -> het."""

    @staticmethod
    def _pkt(op, body):
        import struct
        return bytes([0xC0, 0x91]) + struct.pack("<H", 7 + len(body)) + bytes([0, 0, op]) + body

    def test_chuoi_goi(self):
        from bot import client as client_module
        g = client_module.GameClient("user", "token")
        g.running = True
        g.follow_npc = {1: 41041, 2: 14096}
        gui = []

        def su_kien(sub, rtype=0, style=0, surface=0):
            body = bytes([sub, 0]) + bytes(4) + bytes([rtype]) + bytes(3) + bytes([style]) \
                + bytes(4) + surface.to_bytes(2, "little")
            g._dispatch(0x14, self._pkt(0x14, body))

        def send(op, data=b""):
            gui.append((op, bytes(data)))
            if op == 0x14 and data[:2] == b"\x01\x00":
                su_kien(6, rtype=6, style=0, surface=2)            # hoi surface 2
            elif op == 0x14 and data[:2] == b"\x09\x00":
                g._dispatch(0x1f, self._pkt(0x1f, b"\x07\x00"))   # chon Vo Tuong -> mo bang
            elif op == 0x1f and data[:2] == b"\x03\x00":
                g._dispatch(0x1f, self._pkt(0x1f, b"\x03\x00" + bytes([4, data[2]])))
            elif op == 0x14 and data[:2] == b"\x06\x00":
                su_kien(8)                                         # het su kien

        g.send = send
        g.quest_kich_hoat("npc", 3)
        kq = g.quest_hoi_thoai(chon={"2": 32}, nha_tro=2, im_lang=5.0, toi_da=20.0)
        self.assertEqual(kq, "xong")
        sau = [x for x in gui if x[0] in (0x14, 0x1f)][1:]
        self.assertEqual(sau, [(0x14, b"\x09\x00\x20"), (0x1f, b"\x03\x00\x02"),
                               (0x1f, b"\x0a\x00"), (0x14, b"\x06\x00")])
        self.assertEqual(g._nha_tro_kq, (4, 2))
        self.assertEqual(g.vantieu_roster_ids.get(4), 14096)


class TestPetMangTheoCapNhatGiuaPhien(unittest.TestCase):
    """vuchin 10/10: gui Cuu Soi vao nha tro (`VO TUONG XOA o 4`) ma tab pet GUI van con Cuu Soi -
    `state.carried_pets` chi doc lai khi nhan nguyen danh sach pet luc login."""

    @staticmethod
    def _goi(sub, ent, idx, npc=0):
        import struct
        body = bytes([sub, 0]) + ent + bytes([idx]) + struct.pack("<I", npc) + bytes(2)
        return bytes([0xC0, 0x91]) + struct.pack("<H", 7 + len(body)) + bytes([0, 0, 0x0F]) + body

    def _client(self):
        from bot import client as client_module
        g = client_module.GameClient("user", "token")
        g.self_entity = bytes([0x11]) * 8
        g.follow_slots = {1, 2, 3, 4}
        g.follow_npc = {1: 41048, 2: 14054, 3: 17003, 4: 14096}
        g.state.carried_pets = [(41048, "A"), (14054, "B"), (17003, "C"), (14096, "Cuu Soi")]
        return g

    def test_xoa_vo_tuong_thi_bo_khoi_pet_mang_theo_va_ghi_cache(self):
        from bot import client as client_module
        g = self._client()
        with mock.patch.object(client_module, "save_skill_cache") as ghi:
            g._dispatch(0x0F, self._goi(2, g.self_entity, 4))
        self.assertEqual([p for p, _n in g.state.carried_pets], [41048, 14054, 17003])
        self.assertEqual(g.follow_npc, {1: 41048, 2: 14054, 3: 17003})
        self.assertEqual([p[0] for p in ghi.call_args[0][1]["pets"]], [41048, 14054, 17003])

    def test_them_vo_tuong_giua_phien(self):
        from bot import client as client_module
        g = self._client()
        g._dispatch(0x0F, self._goi(2, g.self_entity, 4))
        with mock.patch.object(client_module, "save_skill_cache"):
            g._dispatch(0x0F, self._goi(1, g.self_entity, 4, npc=18005))
        self.assertEqual([p for p, _n in g.state.carried_pets], [41048, 14054, 17003, 18005])
        g._dispatch(0x0F, self._goi(1, g.self_entity, 4, npc=18005))     # lap -> khong nhan doi
        self.assertEqual(len(g.state.carried_pets), 4)

    def test_cat_nha_tro_xac_nhan_bang_xoa_o(self):
        """Server KHONG gui S:031-003 ma xoa o di theo (log vuchin 10/10) -> van la DA GUI."""
        g = self._client()
        g.running = True
        gui = []

        def send(op, data=b""):
            gui.append((op, bytes(data)))
            if op == 0x1f and data[:2] == b"\x03\x00":
                g._dispatch(0x0F, self._goi(2, g.self_entity, data[2]))

        g.send = send
        self.assertTrue(g.nha_tro_gui(4, cho=1.0))
        self.assertEqual(gui, [(0x1f, b"\x03\x00\x04"), (0x1f, b"\x0a\x00")])

    def test_o_da_trong_thi_khong_gui_lenh_cat(self):
        g = self._client()
        g.running = True
        g.follow_npc.pop(4)
        gui = []
        g.send = lambda op, data=b"": gui.append((op, bytes(data)))
        self.assertTrue(g.nha_tro_gui(4, cho=1.0))
        self.assertEqual(gui, [(0x1f, b"\x0a\x00")])
