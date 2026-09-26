"""ENGINE PARTY MOI: vong nhip + chup anh + anh xa viec -> ham THAT.

Ba thu nay la cho engine moi CHAM vao game, nen cung la cho de de loi moi nhat. Neo lai:
  - chup anh: doc THANG client (L2), mot acc loi khong duoc lam hong ca anh
  - nhip: khong chan, mot nhip no khong duoc giet engine (L0 - party dung im vinh vien la cam)
  - thi hanh: goi dung ham co san trong `client.py`, KHONG viet lai thao tac game
Thiet ke: documents/ENGINE_PARTY_MOI.md
"""
from __future__ import annotations

import io
import os
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import party_engine as E


class _Cli:
    """Client gia - chi co dung nhung thu engine doc/goi."""

    def __init__(self, map_id=23851, kenh=1, danh=False, vat=False, members=0, no=False):
        self.running = True
        self.current_map = map_id
        self.current_channel = kenh
        self.party_members = list(range(members))
        self.flee_mode = True
        self._danh = danh
        self._vat = vat
        self._no = no
        self._pe_xong_chore = True     # mac dinh: da lam xong viec vat (ca rieng se dat False)
        self._pe_xong_daily = True     # mac dinh: da lam xong nhiem vu ngay (o1 + claim 9 o)
        self._co_thuoc = True
        self._co_route = True
        self._tele_hong = False
        self.phuc_than_pending = False
        self.da_goi = []

    def in_di_gioi(self):
        return self.current_map == 49942

    def digioi_minutes_live(self):
        return 120

    def in_combat(self, *a, **k):
        if self._no:
            raise RuntimeError("client hong")
        return self._danh

    def dang_lam_viec_vat(self):
        return self._vat

    # -- cac ham engine goi khi thi hanh --
    def go_to_town(self, city_id, flag=0, *a, **k):
        self.da_goi.append(("go_to_town", int(city_id), int(flag)))
        if not self._tele_hong:
            self.current_map = int(city_id)
        return True

    def build_smart_route(self, dest_map, safe):
        self.da_goi.append(("build_smart_route", dest_map))
        return self._co_route and [("go", dest_map)]

    def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
        self.da_goi.append(("follow_smart_route", dest_map))
        self.current_map = dest_map
        return True

    def navigate_to(self, x, y, flee=True, abort=None, **k):
        self.da_goi.append(("navigate_to", int(x), int(y)))
        return True

    def switch_channel(self, ch, wait=None, retries=None, theo_lenh=False, *a, **k):
        self.da_goi.append(("switch_channel", ch, bool(theo_lenh)))
        self.current_channel = ch
        return True

    def invite_train_party_participants(self, gap=1.0):
        self.da_goi.append(("invite", gap))
        return True

    def invite_members(self, gap=1.0):
        self.da_goi.append(("invite_members", gap))
        return True

    def invite_whitelist_leaders(self, gap=1.0):
        self.da_goi.append(("invite_whitelist", gap))
        return 0

    def in_di_gioi(self):
        return self.current_map == 49942

    def set_party_invite_ready(self, ready=True):
        self.da_goi.append(("invite_ready", ready))

    def combat_ready(self):
        self.da_goi.append(("combat_ready",))

    def start_run_around(self):
        self.da_goi.append(("start_run_around",))

    def stop_run_around(self):
        self.da_goi.append(("stop_run_around",))

    def set_party_strategist(self):
        self.da_goi.append(("set_party_strategist",))

    def follow_path(self, duong, flee=True, abort=None, **k):
        self.da_goi.append(("follow_path", tuple(duong), bool(flee)))
        return True

    def use_phuc_than_items(self):
        self.da_goi.append(("phuc_than",))

    def has_hp_and_sp_items(self):
        return self._co_thuoc

    def buy_hp_sp(self, *a, **k):
        self.da_goi.append(("buy_hp_sp",))

    def enter_di_gioi_safe(self, *a, **k):
        self.da_goi.append(("enter_di_gioi_safe",))
        self.current_map = 49942
        return True

    def set_di_gioi_level(self, lv):
        self.da_goi.append(("set_di_gioi_level", int(lv)))

    def claim_daily_quests(self, heavy=False):
        self.da_goi.append(("claim_daily_quests", heavy))

    def befriend_nearby(self):
        self.da_goi.append(("befriend_nearby",))


def _engine(clients, can=2, map_dich=None, log=None):
    def _doc():
        return [(u, c, u == "l") for u, c in clients]
    return E.PartyEngine(40, _doc, can_bao_nhieu=can, map_dich=map_dich, log=log)


def _start_worker(eng):
    """Ban CHAY THAT: thread cua chinh acc goi `chay_o_day()`. Trong test khong co thread do nen
    tu tao - `AccWorker.start()` co san cho viec nay."""
    for w in eng.workers.values():
        w.start()


class TestChupAnh(unittest.TestCase):
    def test_doc_thang_client_khong_doi_ai_bao_cao(self):
        cl = [("l", _Cli(map_id=23851, kenh=1, members=2)), ("m1", _Cli(map_id=23011, kenh=7))]
        anh = _engine(cl).chup()
        self.assertEqual(sorted(anh.maps()), [23011, 23851])
        self.assertEqual(anh.roster_leader(), 2, "roster phai doc cua LEADER")

    def test_mot_API_LOI_khong_giet_ca_acc(self):
        """Doc TUNG TRUONG doc lap: mot API no (vd `in_combat`) chi mat truong do, acc VAN SONG.

        Boc ca anh trong mot try thi acc do bi coi la CHET -> engine tuong party hong va gom lai
        vo tan. Dat hon nhieu so voi viec mat mot truong."""
        cl = [("l", _Cli(members=2)), ("m1", _Cli(no=True))]
        anh = _engine(cl).chup()
        self.assertEqual(len(anh.accs), 2)
        m1 = [a for a in anh.accs if a.username == "m1"][0]
        self.assertTrue(m1.song, "mot API no ma giet ca acc -> gom lai vo tan")
        self.assertFalse(m1.dang_danh, "truong doc loi thi lay mac dinh an toan")
        self.assertEqual(anh.maps(), [23851], "acc loi khong duoc de ra 'lech map' gia")

    def test_acc_dung_KHONG_song_thi_map_la_None(self):
        c = _Cli(map_id=23011)
        c.running = False
        anh = _engine([("l", _Cli(members=2)), ("m1", c)]).chup()
        self.assertEqual(anh.maps(), [23851])


class TestMotNhip(unittest.TestCase):
    def test_acc_MOI_VAO_engine_lam_viec_vat_TRUOC(self):
        """`_pe_xong_chore` chua co = acc vua login xong -> phai lam viec vat truoc khi bi keo di.
        User 14/09: "vao pt roi bi keo di luon thi no hong viec vat"."""
        c = _Cli(map_id=23011)
        del c._pe_xong_chore
        eng = _engine([("l", _Cli(members=2)), ("m1", c)])
        eng.start()
        try:
            self.assertEqual(eng.nhip()["m1"], E.VIEC_LOGIN_CHORE)
        finally:
            eng.stop()

    def test_nhip_giao_dung_viec_cho_tung_acc(self):
        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _Cli(map_id=23011))]
        eng = _engine(cl)
        eng.start()
        try:
            v = eng.nhip()
            self.assertEqual(v["m1"], E.VIEC_VE_MAP)
        finally:
            eng.stop()

    def test_nhip_KHONG_giao_lai_viec_y_HET(self):
        """Giao lai viec giong het khi worker DANG LAM = huy viec dang chay, acc khong bao gio di
        toi noi. `AccWorker.giao` phai tra False khi viec khong doi.

        (Worker XONG viec thi ve NGHI - luc do giao lai la hop le, do la engine ra lenh tiep.)"""
        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _Cli(map_id=23011))]
        eng = _engine(cl)
        eng.start()
        try:
            eng.nhip()
            _start_worker(eng)
            w = eng.workers["m1"]
            w._viec = E.VIEC_VE_MAP        # dat vao dung trang thai DANG LAM
            self.assertFalse(w.giao(E.VIEC_VE_MAP), "giao lai viec y het -> se huy viec dang chay")
        finally:
            eng.stop()

    def test_mot_nhip_NO_khong_giet_engine(self):
        """L0: party dung im vinh vien la cam. Nhip loi -> bo qua, nhip sau lam lai."""
        eng = _engine([("l", _Cli(members=2))])
        goi = []

        def _no():
            goi.append(1)
            raise RuntimeError("nhip hong")

        eng.nhip = _no
        eng.start()
        try:
            for _ in range(300):
                if len(goi) >= 2:
                    break
                time.sleep(0.01)
            self.assertGreaterEqual(len(goi), 2, "engine chet sau nhip loi dau tien")
        finally:
            eng.stop()


class TestThiHanhGoiHamCoSan(unittest.TestCase):
    """KHONG viet lai thao tac game: moi viec goi thang ham da co trong `client.py`."""

    def _lam(self, viec, cli, dich=None):
        E.thi_hanh(cli, viec, lambda: True, dich=dich)
        return cli.da_goi

    def test_ve_map_BUILD_ROUTE_TRUOC_roi_moi_di(self):
        """Y flow cu (`_do_reform` dong 4356 + 4732): build route truoc, co route moi di.

        Goi `follow_smart_route` tran thi khi router khong dung duoc duong, acc di MU va KET trong
        do. Ca that 16/09 party 41: ca 5 acc nhan `ve_map` luc 12:23:38 roi IM 73 PHUT."""
        c = _Cli(map_id=23011)
        goi = self._lam(E.VIEC_VE_MAP, c, 23851)
        self.assertIn(("build_smart_route", 23851), goi)
        self.assertIn(("follow_smart_route", 23851), goi)
        self.assertLess(goi.index(("build_smart_route", 23851)),
                        goi.index(("follow_smart_route", 23851)))

    def test_KHONG_dung_duoc_duong_thi_KHONG_di_mu(self):
        c = _Cli(map_id=23011)
        c._co_route = False
        self.assertFalse(E.thi_hanh(c, E.VIEC_VE_MAP, lambda: True, dich=23851))
        self.assertNotIn(("follow_smart_route", 23851), c.da_goi, "di mu -> ket khong ai biet")

    def test_ve_map_KHONG_lam_gi_khi_da_dung_cho(self):
        c = _Cli(map_id=23851)
        self.assertEqual(self._lam(E.VIEC_VE_MAP, c, 23851), [])

    def test_doi_kenh_dung_switch_channel(self):
        c = _Cli(kenh=7)
        E.thi_hanh(c, E.VIEC_DOI_KENH, lambda: True, dich=1, kenh_doi_duoc=lambda _c: True)
        self.assertIn(("switch_channel", 1, True), c.da_goi)

    def test_LEADER_moi_con_member_chi_MO_CUA_NHAN(self):
        """Member tu moi ai la acc tu quyet (L1). No chi duoc mo cua nhan loi moi."""
        goi = []
        lead = _Cli()
        lead._pe_la_leader = True
        E.thi_hanh(lead, E.VIEC_LAP_PARTY, lambda: True,
                   moi_party=lambda cli, tom: goi.append(cli))
        self.assertEqual(goi, [lead], "leader khong goi duong moi cua engine cu")
        mem = _Cli()
        mem._pe_la_leader = False
        E.thi_hanh(mem, E.VIEC_LAP_PARTY, lambda: True,
                   moi_party=lambda cli, tom: goi.append(cli))
        self.assertEqual(goi, [lead], "member TU MOI ai do (L1)")
        self.assertIn(("invite_ready", True), mem.da_goi)

    def test_viec_vat_thi_KHONG_DUNG_VAO(self):
        """User 14/09: "khi dang danh PB don va daily quest thi dieu phoi tam thoi ko quay ray"."""
        c = _Cli(vat=True)
        self.assertEqual(self._lam(E.VIEC_VIEC_VAT, c), [])

    def test_train_thi_tat_flee_va_bat_combat(self):
        c = _Cli()
        self._lam(E.VIEC_TRAIN, c)
        self.assertFalse(c.flee_mode)
        self.assertIn(("combat_ready",), c.da_goi)


class TestChoreGOI_LAI_KHOI_CU(unittest.TestCase):
    """Viec vat sau login: GOI THANG `lam_login_chores` cua engine cu, KHONG tu che danh sach.

    Khoi cu co hon hai chuc muc: diem danh, qua 14 ngay, qua quan doan, qua ban be, mo rong tui,
    tu cong diem, nang skill, Ba Dau, skill pet, LO HOANG KIM, donate quan doan, ruong trang bi,
    mua shop... Ba trong so do la NGUON cua bang "Chu y" tren GUI (`_tu_cong_diem` -> diem du,
    `_kiem_han_ba_dau` -> Ba Dau, `process_furnace` -> lo).

    Ban tu che dau tien cua engine moi chi co 9 muc => user mat bang "Chu y" va hang chuc viec vat
    khac ma khong co mot dong log nao bao (16/09: "hinh nhu bi mat cai chu y").
    """

    def test_KHONG_con_danh_sach_tu_che(self):
        s = io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        self.assertNotIn("CHORE = (", s, "van tu che danh sach viec -> lai thieu hang chuc muc")

    def test_danh_dau_DANG_LAM_ngay_tu_dau(self):
        """Chua co co nay thi nhip sau doc `xong_chore` roi giao viec khac VA CAT NGANG chores
        (party 41, 16/09: 15:52:21 login_chore -> 15:52:29 lap_party, chores con chay toi :35)."""
        thay = []
        c = _Cli()
        c._pe_xong_chore = True          # con sot tu lan truoc

        def _cho(_cli):
            thay.append(_cli._pe_xong_chore)

        E.lam_viec_vat(c, chore_fn=_cho)
        self.assertEqual(thay, [False], "khong ha co khi bat dau -> engine tuong da xong")
        self.assertTrue(c._pe_xong_chore)

    def test_goi_khoi_cu_qua_chore_fn(self):
        goi = []
        c = _Cli()
        del c._pe_xong_chore
        self.assertTrue(E.lam_viec_vat(c, chore_fn=goi.append))
        self.assertEqual(goi, [c])
        self.assertTrue(c._pe_xong_chore)

    def test_khoi_cu_NO_khong_lam_ket_acc(self):
        """Mot viec no khong duoc lam acc ngoi mai o `login_chore` - danh dau xong, login sau lam lai."""
        c = _Cli()
        del c._pe_xong_chore

        def _no(_cli):
            raise RuntimeError("chore hong")

        self.assertTrue(E.lam_viec_vat(c, chore_fn=_no))
        self.assertTrue(c._pe_xong_chore)

    def test_co_lenh_moi_thi_NHA_RA_va_KHONG_danh_dau_xong(self):
        c = _Cli()
        del c._pe_xong_chore
        self.assertFalse(E.lam_viec_vat(c, chore_fn=lambda _c: None, con_lam=lambda: False))
        self.assertFalse(getattr(c, "_pe_xong_chore", False),
                         "bi cat ngang ma danh dau xong -> mat het viec vat ca ngay")

    def test_khoi_cu_la_ham_MODULE_LEVEL_goi_duoc(self):
        """Neu no lai bi nhet vao trong `run_account` thi engine moi mat sach lan nua."""
        src = io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8").read()
        i = src.find("def lam_login_chores(")
        self.assertGreater(i, 0, "khoi viec vat khong con la ham goi duoc")
        self.assertEqual(src[i - 1], chr(10), "ham phai o MODULE LEVEL, khong long trong ham khac")


class TestMoiDungDUONG(unittest.TestCase):
    """Hai duong moi KHAC NHAU, y nhu `_invite_party_participants` cua engine cu:
        o MAP TRAIN        -> `invite_train_party_participants` (loc theo map/kenh dang dung)
        cho khac (Di Gioi) -> whitelist truoc, roi `invite_members`
    Dung nham duong o Di Gioi thi leader moi bang bo loc cua map train -> khong ai duoc moi.
    """

    def test_GOI_LAI_ham_cu_chu_khong_chep_logic(self):
        """`_invite_party_participants` da co: whitelist truoc, hai duong train/khac, va
        `_leader_tu_kiem_kenh`. Ban chep dau tien cua engine moi quen ca whitelist lan kiem kenh."""
        goi = []
        c = _Cli(map_id=23851)
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_LAP_PARTY, lambda: True,
                   moi_party=lambda cli, tom: goi.append(tom))
        self.assertEqual(goi, [True], "o map train phai bao `train_on_map=True`")
        self.assertNotIn(("invite", 1.0), c.da_goi, "van tu goi invite -> dang chep lai logic cu")
        self.assertNotIn(("invite_members", 1.0), c.da_goi)
        self.assertIn(("set_party_strategist",), c.da_goi, "quen dat quan su sau khi moi")

    def test_trong_DI_GIOI_bao_train_on_map_FALSE(self):
        """Duong moi o DG khac map train; bao nham la leader moi bang bo loc map train -> khong ai
        duoc moi."""
        goi = []
        c = _Cli(map_id=49942)
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_LAP_PARTY, lambda: True,
                   moi_party=lambda cli, tom: goi.append(tom))
        self.assertEqual(goi, [False])

    def test_khong_co_duong_moi_thi_KHONG_tu_che(self):
        c = _Cli(map_id=23851)
        c._pe_la_leader = True
        self.assertFalse(E.thi_hanh(c, E.VIEC_LAP_PARTY, lambda: True, moi_party=None))
        self.assertEqual(c.da_goi, [])

    def test_member_chi_MO_CUA_du_o_dau(self):
        for _map in (23851, 49942):
            c = _Cli(map_id=_map)
            c._pe_la_leader = False
            E.thi_hanh(c, E.VIEC_LAP_PARTY, lambda: True)
            self.assertEqual(c.da_goi, [("invite_ready", True)], "member tu moi ai do (L1)")


class TestTrongDiGioiPhaiCHAY_TIM_QUAI(unittest.TestCase):
    """Quai trong Di Gioi KHONG tu toi - phai chay long vong.

    Engine cu goi `start_run_around()` o moi duong vao DG (run_party_digioi.py:5941/5964/6049/6357
    - "DG: chay long vong tim quai"). Thieu no thi ca party dung im giua Di Gioi.

    Do that 16/09 party 41 (user: "p41 dung o quang truong"):
        07:52:36 [dtmot] (LEADER) pos=(570, 630) map=49942 combat=False
        07:52:41 [dtmot] (LEADER) pos=(570, 630) map=49942 combat=False
        07:52:46 [dtmot] (LEADER) pos=(570, 630) map=49942 combat=False
    Party DU 4/4, o dung map DG, ma pos khong doi va khong vao tran mot lan nao.
    """

    def test_trong_DG_thi_chay_long_vong(self):
        c = _Cli(map_id=49942)
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertIn(("start_run_around",), c.da_goi,
                      "dung im giua Di Gioi cho quai tu toi")

    def test_o_map_train_thi_DUNG_chay_long_vong(self):
        """Map thuong co tam bai quai co dinh - chay long vong o do la roi khoi bai."""
        c = _Cli(map_id=23851)
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertIn(("stop_run_around",), c.da_goi)
        self.assertNotIn(("start_run_around",), c.da_goi)

    def test_van_bat_combat_o_ca_hai_noi(self):
        for _map in (49942, 23851):
            c = _Cli(map_id=_map)
            E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
            self.assertIn(("combat_ready",), c.da_goi)
            self.assertFalse(c.flee_mode)


class TestKhongVUT_FLOW_CU(unittest.TestCase):
    """RA SOAT 16/09 (user: "viet lai ma sao may flow dang co vut het roi").

    Doi chieu moi `c.<ham>()` engine cu goi trong `run_account` voi nhung gi engine moi goi. Tam
    cai da bi vut va phai va nguoc: `dt_phase`, `mob_spot`, client sau relogin, moi sai duong,
    khong lap party trong DG, `_handle_auto_team_dungeon`, `start_run_around`, thoat khi xong DG
    thuan. Bai nay giu nhung cai con lai.
    """

    def test_lap_party_xong_thi_DAT_QUAN_SU(self):
        """Engine cu goi `set_party_strategist` o 6 cho. Thieu = party khong co quan su."""
        c = _Cli()
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_LAP_PARTY, lambda: True, moi_party=lambda cli, tom: None)
        self.assertIn(("set_party_strategist",), c.da_goi)

    def test_LEADER_di_DUONG_CAPTURE_de_keo_ca_party(self):
        """Bai quai xa: duong thang di xuyen vung quai, va member khong duoc keo. Engine cu:
        "sau khi LAP PARTY xong, _start_training moi cho leader follow_path KEO CA PARTY"."""
        c = _Cli()
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200),
                   duong_ra_spot=[(10, 20), (30, 40)])
        self.assertIn(("follow_path", ((10, 20), (30, 40)), False), c.da_goi)
        self.assertNotIn(("navigate_to", 100, 200), c.da_goi)

    def test_khong_co_duong_capture_thi_navigate_thang(self):
        c = _Cli()
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200), duong_ra_spot=None)
        self.assertIn(("navigate_to", 100, 200), c.da_goi)

    def test_MEMBER_khong_tu_di_duong_capture(self):
        """Duong capture la de LEADER keo; member tu di la moi nguoi mot huong."""
        c = _Cli()
        c._pe_la_leader = False
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200),
                   duong_ra_spot=[(10, 20)])
        self.assertIn(("navigate_to", 100, 200), c.da_goi)
        self.assertNotIn(("follow_path", ((10, 20),)), c.da_goi)

    def test_train_thi_duy_tri_PHUC_THAN(self):
        c = _Cli()
        c._pe_pcfg = {"use_phuc_than": True}
        c.phuc_than_pending = True
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertIn(("phuc_than",), c.da_goi)

    def test_het_thuoc_thi_MUA(self):
        c = _Cli()
        c._pe_pcfg = {"buy_hp": True}
        c._co_thuoc = False
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertIn(("buy_hp_sp",), c.da_goi)

    def test_user_TAT_thi_KHONG_lam(self):
        """`_pe_pcfg` truoc day KHONG AI GAN -> pcfg rong -> moi `get(co, True)` ra True: user tat
        tinh nang nao thi engine van lam tinh nang do. Hong am tham."""
        c = _Cli()
        c._pe_pcfg = {"use_phuc_than": False, "buy_hp": False, "buy_sp": False}
        c.phuc_than_pending = True
        c._co_thuoc = False
        E.thi_hanh(c, E.VIEC_TRAIN, lambda: True)
        self.assertNotIn(("phuc_than",), c.da_goi)
        self.assertNotIn(("buy_hp_sp",), c.da_goi)


class TestVaoDiGioiLamY_FLOW_CU(unittest.TestCase):
    """Y flow cu (`run_account`, nhanh `elif is_digioi`, dong 5473-5622):
        1. Ho Phu khi con < 15 phut
        2. DAT CAP QUAI DG  (`set_di_gioi_level` <- cap dieu phoi chot)
        3. vao DG
        4. sau khi vao: `claim_daily_quests(heavy=False)` + `befriend_nearby()`

    Bo buoc 2 = ca party danh cap quai MAC DINH thay vi cap user chon.
    Bo `befriend_nearby` = PB to doi co luc khong moi duoc ai: loi moi PHONG PB di theo roleId tu
    friend-list (KNOWLEDGE.md: "can cache `name -> roleId` tu nguon nay").
    """

    def test_dat_CAP_QUAI_truoc_khi_vao(self):
        c = _Cli(map_id=21011)
        E.thi_hanh(c, E.VIEC_DI_GIOI, lambda: True, cap_dg=5)
        self.assertIn(("set_di_gioi_level", 5), c.da_goi, "vao DG voi cap quai mac dinh")
        self.assertLess(c.da_goi.index(("set_di_gioi_level", 5)),
                        c.da_goi.index(("enter_di_gioi_safe",)), "dat cap SAU khi vao thi vo ich")

    def test_sau_khi_vao_thi_claim_nhe_va_BEFRIEND(self):
        c = _Cli(map_id=21011)
        E.thi_hanh(c, E.VIEC_DI_GIOI, lambda: True)
        self.assertIn(("claim_daily_quests", False), c.da_goi)
        self.assertIn(("befriend_nearby",), c.da_goi, "thieu -> PB to doi khong moi duoc theo roleId")

    def test_HO_PHU_chi_khi_user_BAT(self):
        goi = []
        c = _Cli(map_id=21011)
        c._pe_pcfg = {"use_digioi_ho_phu": False}
        E.thi_hanh(c, E.VIEC_DI_GIOI, lambda: True, ho_phu=lambda cli: goi.append(cli))
        self.assertEqual(goi, [], "user tat ma van dung Ho Phu")

        c2 = _Cli(map_id=21011)
        c2._pe_pcfg = {"use_digioi_ho_phu": True}
        E.thi_hanh(c2, E.VIEC_DI_GIOI, lambda: True, ho_phu=lambda cli: goi.append(cli))
        self.assertEqual(goi, [c2])

    def test_ho_phu_LOI_khong_chan_viec_vao_DG(self):
        c = _Cli(map_id=21011)
        c._pe_pcfg = {"use_digioi_ho_phu": True}

        def _no(_cli):
            raise RuntimeError("ho phu hong")

        self.assertTrue(E.thi_hanh(c, E.VIEC_DI_GIOI, lambda: True, ho_phu=_no))
        self.assertIn(("enter_di_gioi_safe",), c.da_goi)


class TestWorkerNHA_THREAD_khi_acc_STOP(unittest.TestCase):
    """Worker chay tren THREAD CUA ACC. Vong no phai thoat khi acc bi STOP/rot.

    Thieu thi mode `digioi` thuan goi `stop_account` xong ma thread van song -> acc khong bao gio
    dung han (user 16/09: "p46 p54, mode Di gioi -> het tiem di gioi roi ma deo tat acc").
    """

    def test_nen_dung_True_thi_vong_THOAT(self):
        dung = [False]
        w = E.AccWorker("u", _Cli(), lambda _c, _v, _l: None)
        th = threading.Thread(target=lambda: w.chay_o_day(nen_dung=lambda: dung[0]), daemon=True)
        th.start()
        try:
            w.giao(E.VIEC_TRAIN)
            time.sleep(0.3)
            self.assertTrue(th.is_alive())
            dung[0] = True                     # acc bi STOP
            th.join(timeout=3.0)
            self.assertFalse(th.is_alive(), "acc da STOP ma worker van quay -> acc khong tat han")
        finally:
            w.stop()

    def test_khong_co_nen_dung_thi_van_chay_nhu_cu(self):
        w = E.AccWorker("u", _Cli(), lambda _c, _v, _l: None)
        th = threading.Thread(target=w.chay_o_day, daemon=True)
        th.start()
        try:
            time.sleep(0.2)
            self.assertTrue(th.is_alive())
        finally:
            w.stop()
            th.join(timeout=2.0)

    def test_nen_dung_NO_khong_giet_worker(self):
        def _no():
            raise RuntimeError("hong")

        w = E.AccWorker("u", _Cli(), lambda _c, _v, _l: None)
        th = threading.Thread(target=lambda: w.chay_o_day(nen_dung=_no), daemon=True)
        th.start()
        try:
            time.sleep(0.3)
            self.assertTrue(th.is_alive(), "nen_dung no ma giet luon worker")
        finally:
            w.stop()
            th.join(timeout=2.0)


class TestStopTatCa_PHAI_CAT_NGANG_viec_dang_lam(unittest.TestCase):
    """User bam "Stop tat ca" -> acc engine moi phai dung NGAY, khong chay het viec roi moi dung.

    Viec chan co the dai hang chuc phut (di duong, danh PB to doi 10-20 phut). `nen_dung` chi kiem
    o DAU VONG la khong du - phai truyen xuong tan `abort=` cua thao tac dang chay.
    User 16/09: "an stop tat ca -> acc theo co che moi ko thay tat".
    """

    def test_acc_bi_STOP_thi_viec_dang_chay_NHA_RA(self):
        dung = [False]
        xong = threading.Event()

        def _lam(_c, _viec, con_lam):
            while con_lam():            # viec chan dai
                time.sleep(0.01)
            xong.set()

        w = E.AccWorker("u", _Cli(), _lam)
        th = threading.Thread(target=lambda: w.chay_o_day(nen_dung=lambda: dung[0]), daemon=True)
        th.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            time.sleep(0.3)
            self.assertFalse(xong.is_set(), "viec chua chay")
            dung[0] = True              # user bam Stop
            self.assertTrue(xong.wait(3), "Stop roi ma viec chan van chay tiep")
            th.join(timeout=3.0)
            self.assertFalse(th.is_alive(), "worker khong nha thread sau Stop")
        finally:
            w.stop()

    def test_abort_truyen_xuong_ham_client_co_ke_acc_STOP(self):
        thay = {}

        class _C(_Cli):
            def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
                thay["abort"] = abort
                return True

        w = E.AccWorker("u", _C(map_id=23011), lambda c, v, con: E.thi_hanh(
            c, v, con, dich=23851))
        th = threading.Thread(target=lambda: w.chay_o_day(nen_dung=lambda: True), daemon=True)
        th.start()
        th.join(timeout=2.0)
        w.stop()
        # nen_dung=True ngay tu dau -> vong thoat, khong chay viec nao
        self.assertNotIn("abort", thay)


class TestEngineTU_THOAT_khi_party_dung_han(unittest.TestCase):
    """Y `_party_watcher` cua engine cu:
        `if not accs or not any(is_account_running(u) for u in accs): return`

    Thieu buoc nay thi sau khi user bam "Stop tat ca", thread nhip van quay mai va giu tham chieu
    toi client da dong (user 16/09: "an stop tat ca -> acc theo co che moi ko thay tat").
    """

    def test_khong_acc_nao_song_thi_THOAT_LUONG(self):
        cl = [("l", _Cli(members=2)), ("m1", _Cli())]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            time.sleep(0.3)
            self.assertTrue(eng._th.is_alive())
            for _u, c in cl:
                c.running = False           # user bam Stop tat ca
            eng._th.join(timeout=4.0)
            self.assertFalse(eng._th is not None and eng._th.is_alive(),
                             "party da dung han ma thread nhip van quay")
        finally:
            eng.stop()

    def test_con_MOT_acc_song_thi_VAN_CHAY(self):
        cl = [("l", _Cli(members=2)), ("m1", _Cli())]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            cl[1][1].running = False
            time.sleep(0.5)
            self.assertTrue(eng._th.is_alive(), "con acc song ma da bo party")
        finally:
            eng.stop()

    def test_thoat_thi_DUNG_luon_worker(self):
        cl = [("l", _Cli(members=2))]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            cl[0][1].running = False
            eng._th.join(timeout=4.0)
            self.assertTrue(eng._dung.is_set(), "thoat ma khong dung worker -> thread treo lai")
        finally:
            eng.stop()


class TestWorkerPHAI_LOG_LOI(unittest.TestCase):
    """Im lang la benh nang nhat cua engine cu - engine moi khong duoc phep tai lap.

    Worker truoc day chi luu loi vao `loi_cuoi` roi im: acc lap lai mot viec loi hang tieng ma
    KHONG MOT DONG NAO bao. Ca that 16/09 party 41: ca 5 acc nhan `ve_map` luc 12:23:38 roi im
    73 phut, phai doc log cua ENGINE moi biet chung con song.
    """

    def test_viec_LOI_thi_phai_LOG(self):
        bao = []

        class _Log:
            @staticmethod
            def warning(*a, **k):
                bao.append(a)

            @staticmethod
            def info(*a, **k):
                pass

        def _no(_c, _v, _l):
            raise RuntimeError("no thu")

        w = E.AccWorker("u", _Cli(), _no, log=_Log)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if bao:
                    break
                time.sleep(0.01)
            self.assertTrue(bao, "viec loi ma khong log -> acc im, khong ai biet")
            self.assertIn("LOI", bao[0][0])
        finally:
            w.stop()

    def test_van_giu_loi_cuoi_de_tra_cuu(self):
        def _no(_c, _v, _l):
            raise RuntimeError("no thu")

        w = E.AccWorker("u", _Cli(), _no)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if w.loi_cuoi is not None:
                    break
                time.sleep(0.01)
            self.assertIsNotNone(w.loi_cuoi)
        finally:
            w.stop()

    def test_khong_co_log_thi_van_chay_tiep(self):
        dem = []

        def _no(_c, _v, _l):
            dem.append(1)
            raise RuntimeError("no")

        w = E.AccWorker("u", _Cli(), _no, log=None)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(300):
                if len(dem) >= 2:
                    break
                time.sleep(0.01)
            self.assertGreaterEqual(len(dem), 2, "khong co log thi worker chet")
        finally:
            w.stop()


class TestGIAO_so_voi_VIEC_DA_XEP(unittest.TestCase):
    """`giao()` phai so voi viec MOI NHAT DA XEP, khong chi so voi viec DANG CHAY.

    Worker co the dang KET trong mot viec chan dai (login chores, di duong, PB to doi) nen `_viec`
    con la viec cu hang phut sau khi da xep viec moi. So nham thi MOI NHIP engine lai tuong "viec
    doi" -> set `_huy` lien tuc -> moi viec chan vua bat dau la bi abort ngay.

    Ca that 16/09 party 41 (user: "p41 van dung o trac quan mai"):
        15:52:29 ENGINE: dt806 -> lap_party
        15:52:30 ENGINE: dt806 -> ve_map
        15:52:31 ENGINE: dt806 -> ve_map      <- giao LAI moi giay
        15:52:34 ENGINE: dt806 -> ve_map
    Acc dung nguyen mot cho ca ngay vi khong viec nao song qua duoc mot giay.
    """

    def test_giao_lai_viec_DA_XEP_thi_tra_False(self):
        w = E.AccWorker("u", _Cli(), lambda *_a: None)
        self.assertTrue(w.giao(E.VIEC_VE_MAP), "lan dau phai nhan")
        self.assertFalse(w.giao(E.VIEC_VE_MAP), "giao lai y het -> huy viec vua xep")
        self.assertFalse(w.giao(E.VIEC_VE_MAP))

    def test_viec_KHAC_thi_van_nhan(self):
        w = E.AccWorker("u", _Cli(), lambda *_a: None)
        w.giao(E.VIEC_VE_MAP)
        self.assertTrue(w.giao(E.VIEC_DOI_KENH))

    def test_worker_DANG_KET_ma_engine_giao_lai_thi_KHONG_huy(self):
        """Day la ca that: worker ket trong viec chan, engine nhip 1s giao lai cung mot viec."""
        vet = []
        cho = threading.Event()

        def _lam(_c, viec, con_lam):
            vet.append(viec)
            while con_lam():
                time.sleep(0.01)
            cho.set()

        w = E.AccWorker("u", _Cli(), _lam)
        w.start()
        try:
            w.giao(E.VIEC_LOGIN_CHORE)
            for _ in range(200):
                if vet:
                    break
                time.sleep(0.01)
            w.giao(E.VIEC_VE_MAP)          # engine doi y
            for _ in range(300):
                if len(vet) >= 2:
                    break
                time.sleep(0.01)
            self.assertEqual(vet[-1], E.VIEC_VE_MAP)
            cho.clear()
            for _ in range(5):             # engine nhip 1s giao lai CUNG viec do
                self.assertFalse(w.giao(E.VIEC_VE_MAP))
            time.sleep(0.4)
            self.assertFalse(cho.is_set(), "viec dang chay bi huy du engine giao y het")
        finally:
            w.stop()


class TestXONG_VIEC_thi_NGHI_khong_tu_lap(unittest.TestCase):
    """Worker lam xong viec thi NGHI cho lenh moi - KHONG tu chay lai chinh viec do.

    Truoc day `_viec` giu nguyen nen vong sau lam lai y het. Cong voi cua `dang_ban` (engine khong
    ra lenh de len acc dang ban) thanh khoa chat: acc lam mot viec lap vo tan, engine khong bao gio
    giao duoc viec moi.

    Ca that 16/09 party 41 (user: "p41 lai dung o trac quan, ko lam gi ca"):
        16:49:19 XONG viec vat sau login
        16:49:19 bat dau viec vat sau login     <- lap lai ngay
        16:49:25 XONG / 16:49:26 bat dau ...
    """

    def test_xong_thi_viec_ve_NGHI(self):
        w = E.AccWorker("u", _Cli(), lambda *_a: None)
        w.start()
        try:
            w.giao(E.VIEC_LOGIN_CHORE)
            for _ in range(300):
                if w.viec_hien_tai() == E.VIEC_NGHI:
                    break
                time.sleep(0.01)
            self.assertEqual(w.viec_hien_tai(), E.VIEC_NGHI,
                             "viec giu nguyen -> worker tu lap lai vo tan")
        finally:
            w.stop()

    def test_KHONG_chay_lai_viec_do_lan_hai(self):
        dem = []
        w = E.AccWorker("u", _Cli(), lambda _c, v, _l: dem.append(v))
        w.start()
        try:
            w.giao(E.VIEC_LOGIN_CHORE)
            time.sleep(1.5)
            self.assertEqual(dem.count(E.VIEC_LOGIN_CHORE), 1,
                             "chay %d lan -> dang tu lap" % dem.count(E.VIEC_LOGIN_CHORE))
        finally:
            w.stop()

    def test_co_viec_MOI_thi_lam_ngay_khong_bi_ghi_de_bang_NGHI(self):
        dem = []
        w = E.AccWorker("u", _Cli(), lambda _c, v, _l: dem.append(v) or time.sleep(0.2))
        w.start()
        try:
            w.giao(E.VIEC_LOGIN_CHORE)
            time.sleep(0.1)
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if E.VIEC_VE_MAP in dem:
                    break
                time.sleep(0.01)
            self.assertIn(E.VIEC_VE_MAP, dem, "viec moi bi nuot khi worker ve NGHI")
        finally:
            w.stop()

    def test_engine_VAN_giao_lai_duoc_khi_dieu_kien_chua_doi(self):
        """Di duong chua toi noi -> nhip sau engine giao LAI `ve_map`. Do la viec cua ENGINE,
        khong phai worker tu lap."""
        class _KhongToi(_Cli):
            def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
                self.da_goi.append(("follow_smart_route", dest_map))
                return False            # di mai khong toi

        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _KhongToi(map_id=23011))]
        eng = _engine(cl, can=1)
        eng.start()
        try:
            for _ in range(3):
                self.assertEqual(eng.nhip()["m1"], E.VIEC_VE_MAP)
        finally:
            eng.stop()


class TestDICH_khi_ca_party_DA_CUNG_MAP(unittest.TestCase):
    """Ca party da cung map (dang o THANH DI NGANG QUA) -> dich phai la MAP TRAIN.

    Truoc day lay "map dong nguoi nhat" nen no tra ve CHINH CAI THANH DANG DUNG: viec `ve_map`
    thay "da o do roi" -> tra ve ngay -> worker nghi -> engine giao lai -> vong 1 giay, party dung
    yen o thanh ca ngay.

    Ca that 16/09 party 41 (user: "p41 lai lap pt o Trac quan"):
        17:15:26 ENGINE: dt806..dt810 -> ve_map
        17:15:27 ENGINE: dt806..dt810 -> ve_map
        17:15:28 ENGINE: dt806..dt810 -> ve_map
    """

    def test_cung_map_thi_dich_la_MAP_TRAIN(self):
        cl = [("l", _Cli(map_id=12001, members=2)), ("m1", _Cli(map_id=12001))]
        eng = _engine(cl, can=1, map_dich=23851)
        self.assertEqual(eng._map_dich_hien_tai(), 23851,
                         "dich la chinh cho dang dung -> khong bao gio di dau")

    def test_lech_map_thi_van_don_ve_mot_cho(self):
        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _Cli(map_id=12001))]
        eng = _engine(cl, can=1, map_dich=None)
        self.assertEqual(eng._map_dich_hien_tai(), 23851, "khong don ve map dong nguoi nhat")

    def test_dich_nam_trong_so_map_dang_dung_thi_uu_tien_no(self):
        cl = [("l", _Cli(map_id=12001, members=2)), ("m1", _Cli(map_id=23851))]
        eng = _engine(cl, can=1, map_dich=23851)
        self.assertEqual(eng._map_dich_hien_tai(), 23851)

    def test_KHONG_co_map_dich_thi_giu_nguyen_cach_cu(self):
        cl = [("l", _Cli(map_id=12001, members=2)), ("m1", _Cli(map_id=12001))]
        eng = _engine(cl, can=1, map_dich=None)
        self.assertEqual(eng._map_dich_hien_tai(), 12001)


class TestKEU_LEN_khi_viec_QUAY_VONG(unittest.TestCase):
    """Cung mot viec duoc giao lai qua nhieu lan lien tiep = no chay xong NGAY ma khong doi duoc
    gi (vd `ve_map` ma dich la chinh cho dang dung).

    Truoc day kieu nay quay CA NGAY trong im lang - phai doc log ENGINE moi thay, con acc thi
    "dung yen khong lam gi" (party 41, 16/09, ba lan lien tiep trong mot ngay).
    """

    def test_giao_lai_qua_nhieu_lan_thi_CANH_BAO(self):
        bao = []

        class _Log:
            @staticmethod
            def warning(*a, **k):
                bao.append(a)

            @staticmethod
            def info(*a, **k):
                pass

            @staticmethod
            def exception(*a, **k):
                pass

        class _KhongToi(_Cli):
            def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
                return False

        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _KhongToi(map_id=23011))]
        eng = _engine(cl, can=1, log=_Log)
        for _ in range(E.LAP_CANH_BAO + 1):
            eng.nhip()
        self.assertTrue([b for b in bao if "quay vong" in str(b)],
                        "viec giao lai %d lan ma khong keu" % E.LAP_CANH_BAO)

    def test_viec_DOI_thi_dem_lai_tu_dau(self):
        eng = _engine([("l", _Cli(members=2))], can=1)
        eng._dem_lap = {"l": (E.VIEC_VE_MAP, 10)}
        eng.nhip()
        self.assertNotEqual(eng._dem_lap.get("l", (None, 0))[1], 11)

    def test_train_va_nghi_KHONG_tinh_la_quay_vong(self):
        """Hai viec nay lap moi nhip la BINH THUONG - dang danh thi giao lai hoai."""
        eng = _engine([("l", _Cli(members=2))], can=1)
        for _ in range(E.LAP_CANH_BAO + 5):
            eng.nhip()
        self.assertNotIn("l", eng._dem_lap)


class TestGOM_la_VE_THANH_TAP_KET(unittest.TestCase):
    """GOM = TELEPORT ve thanh tap ket, khong phai di bo qua cong toi "map dong nguoi nhat".

    Engine cu: `_do_reform` -> `_chot_thanh_tap_ket` -> `go_to_town`.
    Ban dau engine moi lay `kh["map"]` cua dieu phoi lam dich va goi `follow_smart_route` - nhung
    `kh["map"]` CHI LA MAP DONG NGUOI NHAT (thong tin trang thai), KHONG phai dich de di. Ket qua:
    moi acc di mot noi, hoac di toi chinh cho dang dung roi tra ve ngay.

    Ca that 16/09 party 41 (user: "dua thi o trac quan, dua thi o giang dong"):
        18:43:38 dieu phoi chot 'gom' - party dang o 2 MAP khac nhau [12001, 18000]
        18:45:01..18:45:13 ENGINE: dt806..dt810 -> ve_map   (lap moi ~10 giay, khong ai toi dau)
    """

    def test_GOM_di_bang_reform_gen_KHONG_dich_thang(self):
        """`gom` -> `_dieu_phoi_thi_hanh` bump `reform_gen` MOT nhat (cooldown 180s), roi ca party
        ve thanh theo gen do. Dich thang `kh["viec"]` la giao lai moi giay, dap lenh dang chay."""
        self.assertEqual(E.DICH_VIEC[E.DP_GOM], E.VIEC_NGHI)

    def test_ve_thanh_dung_go_to_town_KHONG_di_bo(self):
        c = _Cli(map_id=18000)
        E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=(12061, 2))
        self.assertIn(("go_to_town", 12061, 2), c.da_goi)
        self.assertNotIn(("follow_smart_route", 12061), c.da_goi, "di bo ve thanh -> lau va hay ket")

    def test_PHAI_truyen_dung_FLAG_cua_thanh(self):
        """Moi thanh mot flag rieng (Trac Quan 0, Nghiep Thanh 2, Cu Loc 3, Bac Hai 1,
        Kien Nghiep 9). Truyen thieu la bay ve NHAM THANH.
        User 16/09: "deo gi ma tele lien tuc lai con bi sai flag"."""
        for _city, _flag in ((12061, 2), (12011, 3), (11011, 1), (18001, 9)):
            c = _Cli(map_id=18000)
            E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=(_city, _flag))
            self.assertIn(("go_to_town", _city, _flag), c.da_goi,
                          "thanh %d di voi flag sai" % _city)

    def test_da_o_thanh_roi_thi_KHONG_tele_lai(self):
        c = _Cli(map_id=12001)
        E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=(12001, 0))
        self.assertEqual(c.da_goi, [], "tele lai cho dang dung -> roi party vo ich")

    def test_tele_xong_ma_MAP_KHONG_DOI_thi_bao_THAT_BAI(self):
        """`go_to_town` co the tra True trong khi server chua doi map (thanh chua mo, dang trong
        tran). Khong kiem thi acc TELE LIEN TUC."""
        c = _Cli(map_id=18000)
        c._tele_hong = True
        self.assertFalse(E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=(12061, 2)))

    def test_KHONG_biet_thanh_thi_khong_di_bua(self):
        c = _Cli(map_id=18000)
        self.assertFalse(E.thi_hanh(c, E.VIEC_VE_THANH, lambda: True, dich=None))
        self.assertEqual(c.da_goi, [])


class TestRA_SOAT_doi_chieu_flow_cu(unittest.TestCase):
    """RA SOAT 16/09 (user: "ra soat lai tat ca nhung cai da viet xem cai nao tu bia thi xem lai
    cai da co"). Doi chieu TUNG loi goi trong `thi_hanh` voi cho tuong ung trong engine cu.
    """

    def test_doi_kenh_hoi_BA_MOC_AN_TOAN(self):
        """Doi kenh = doi INSTANCE. Gui giua tran thi server BO QUA ma bot tuong da doi; gui giua
        event -> `S:000-000` ma 47 -> DUT KET NOI (07/09: nam acc dis trong 32 giay).
        Engine cu luon hoi `_kenh_doi_duoc_ngay` truoc."""
        c = _Cli(kenh=7)
        self.assertFalse(E.thi_hanh(c, E.VIEC_DOI_KENH, lambda: True, dich=1,
                                    kenh_doi_duoc=lambda _cli: False))
        self.assertEqual(c.da_goi, [], "doi kenh giua tran -> dut ket noi")

    def test_doi_kenh_truyen_theo_lenh(self):
        """Engine cu: `switch_channel(..., theo_lenh=True)` - bao client day la LENH DIEU PHOI."""
        c = _Cli(kenh=7)
        E.thi_hanh(c, E.VIEC_DOI_KENH, lambda: True, dich=1, kenh_doi_duoc=lambda _cli: True)
        self.assertIn(("switch_channel", 1, True), c.da_goi, "thieu co `theo_lenh`")

    def test_follow_path_phai_FLEE_FALSE(self):
        """Engine cu: `c.follow_path(path, flee=False, abort=_abs)`. De flee mac dinh True thi acc
        bo chay moi lan gap quai va khong bao gio keo party toi noi."""
        c = _Cli()
        c._pe_la_leader = True
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200), duong_ra_spot=[(1, 2)])
        self.assertIn(("follow_path", ((1, 2),), False), c.da_goi, "keo party ma van flee")

    def test_navigate_ra_spot_co_XE_DICH(self):
        """Engine cu: `navigate_to(*_jitter(spot), ...)` - ca party navigate y het mot diem thi
        chung chong len nhau."""
        goi = []
        c = _Cli()
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200),
                   xe_dich=lambda pt: goi.append(pt) or (pt[0] + 10, pt[1] - 10))
        self.assertEqual(goi, [(100, 200)])
        self.assertIn(("navigate_to", 110, 190), c.da_goi)

    def test_toi_bai_thi_BAT_GHI_THONG_KE(self):
        """Engine cu: `_set_train_block_stats_spot(spot, enabled=True)` ngay truoc `combat_ready`."""
        goi = []
        c = _Cli()
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200),
                   ghi_thong_ke=lambda spot, bat: goi.append((spot, bat)))
        self.assertEqual(goi, [((100, 200), True)])


class TestPBDoiDungCUA_RIENG(unittest.TestCase):
    """Member cho phong PB KHONG duoc dung cua party THUONG.

    `set_party_invite_ready(True)` la cua party thuong (`0x0d/0900`). Mo no luc dang cho phong PB
    vua khong giup gi (loi moi PB di duong `0x2f/0f00` rieng, `_on_dungeon` tu accept + ready),
    vua cho loi moi party thuong lot vao giua chung.
    """

    def test_member_KHONG_mo_gate_party_thuong(self):
        c = _Cli()
        E.thi_hanh(c, E.VIEC_PB_DOI_THEO, lambda: True)
        self.assertNotIn(("invite_ready", True), c.da_goi, "mo nham cua party thuong")

    def test_member_bat_auto_accept_de_nhan_loi_moi_PHONG(self):
        c = _Cli()
        E.thi_hanh(c, E.VIEC_PB_DOI_THEO, lambda: True)
        self.assertTrue(getattr(c, "auto_accept_party", False),
                        "khong bat auto accept -> `_on_dungeon` bo qua loi moi phong PB")

    def test_member_KHONG_danh_le_trong_luc_cho(self):
        c = _Cli()
        c.flee_mode = False
        E.thi_hanh(c, E.VIEC_PB_DOI_THEO, lambda: True)
        self.assertTrue(c.flee_mode)

    def test_GOI_LAI_handle_auto_team_dungeon_chu_khong_goi_tho(self):
        """`_handle_auto_team_dungeon` lo retry, `team_dungeon_skip_all`, dong doi ROT giua pho ban,
        `run_event_pre_dungeon` (doi qua su kien truoc PB) va thu tu level. Goi
        `do_team_dungeon` tho la vut het nhung cai do."""
        goi = []
        tho = []

        class _C(_Cli):
            def do_team_dungeon(self, level):
                tho.append(int(level))
                return True

        c = _C()
        E.thi_hanh(c, E.VIEC_PB_DOI, lambda: True, dich=80,
                   chay_pb_doi=lambda cli, lv: goi.append((cli, lv)) or True)
        self.assertEqual(goi, [(c, 80)])
        self.assertEqual(tho, [], "van goi `do_team_dungeon` tho -> mat retry/skip/dong doi rot")

    def test_KHONG_dat_han_cho_cho_PB(self):
        """Engine cu tung co watchdog 180s va no keo CA 4 MEMBER ra relogin GIUA pho ban, pha nat
        luot PB. PB chay 10-20 phut la BINH THUONG."""
        s = io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        i = s.find("if viec == VIEC_PB_DOI:")
        khoi = s[i:i + 700]
        for _cam in ("timeout", "deadline", "time.time()"):
            self.assertNotIn(_cam, khoi, "dat han cho PB -> keo ca party ra giua pho ban")


class TestKhongSPAM_GUI(unittest.TestCase):
    """GUI "not responding" ngay lan chay dau tien cua engine moi (15/09).

    `set_account_activity` mac dinh tao TASK MOI (tang `_ACC_TASK_SEQ`, dat lai `start`). Goi no
    moi nhip cho moi acc = 62 task moi/giay voi 14 party; GUI doc `seq` de biet co gi doi nen no
    ve lai bang LIEN TUC tren main thread Tk -> treo.
    """

    def _dem(self, so_nhip=5, doi_viec_o_nhip=None):
        bao = []
        c_l = _Cli(map_id=23851, members=2)
        c_m = _Cli(map_id=23011)
        eng = _engine([("l", c_l), ("m1", c_m)], can=2)
        eng._bao_gui = lambda u, mo_ta, pha: bao.append((u, pha))
        for i in range(so_nhip):
            if doi_viec_o_nhip is not None and i == doi_viec_o_nhip:
                c_m.current_map = 23851        # het lech map -> viec doi
            eng.nhip()
        return bao

    def test_viec_KHONG_doi_thi_chi_bao_MOT_lan(self):
        bao = self._dem(so_nhip=10)
        self.assertLessEqual(len(bao), 2,
                             "bao GUI moi nhip -> 62 task moi/giay -> Tk treo (%d lan)" % len(bao))

    def test_viec_DOI_thi_PHAI_bao(self):
        bao = self._dem(so_nhip=6, doi_viec_o_nhip=3)
        self.assertGreaterEqual(len(bao), 2, "viec doi ma khong bao -> GUI hien trang thai cu")

    def test_nhip_van_giao_viec_binh_thuong(self):
        """Loc bao GUI KHONG duoc anh huong toi viec giao lenh."""
        c_l = _Cli(map_id=23851, members=2)
        c_m = _Cli(map_id=23011)
        eng = _engine([("l", c_l), ("m1", c_m)], can=2)
        for _ in range(5):
            self.assertEqual(eng.nhip()["m1"], E.VIEC_VE_MAP)


class TestRaBaiXongLaDANH(unittest.TestCase):
    """`viec_dang_lam` trong anh chup la VIEC DUOC GIAO, KHONG phai "da toi noi".

    Neu bat nhip phai doi viec (`ra_spot` -> `train`) thi engine giao `ra_spot` MAI MAI va acc
    dung im ngay tai bai quai. Cung ho voi vong `login_chore` <-> `viec_vat` da thay o lan chay
    dau tien (15/09).
    """

    def test_toi_bai_la_bat_combat_ngay(self):
        c = _Cli()
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=(100, 200))
        self.assertIn(("combat_ready",), c.da_goi, "ra toi bai roi dung im, khong danh")
        self.assertFalse(c.flee_mode)

    def test_bi_CAT_NGANG_thi_KHONG_bat_combat(self):
        """Lenh moi toi giua duong -> dung lai, khong duoc bat danh o cho dung do."""
        c = _Cli()
        E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: False, dich=(100, 200))
        self.assertNotIn(("combat_ready",), c.da_goi)

    def test_khong_co_bai_thi_khong_di_bua(self):
        c = _Cli()
        self.assertFalse(E.thi_hanh(c, E.VIEC_RA_SPOT, lambda: True, dich=None))
        self.assertEqual(c.da_goi, [])


class TestKhongVONG_NONG(unittest.TestCase):
    """GUI "not responding" lan chay thu hai (15/09) - nguyen nhan la VONG NONG.

    `train` / `pb_doi_theo` / `viec_vat` chi set co roi return NGAY. Khong co nhip toi thieu thi
    worker quay vai nghin lan/giay; 62 worker = 62 vong nong an sach CPU, main thread Tk doi.

    Repo nay da dinh dung kieu do mot lan (L10, p5 13:15-13:20): "mot vong nong cua acc `continue`
    khong ngu -> 8.000 vong/giay -> bo doi luong dieu phoi -> ke hoach dong bang 5 phut".

    DO THAT so vong/giay, khong doc chu trong source.
    """

    def _dem_vong(self, giay=1.0):
        dem = [0]

        def _lam(_c, _viec, _con):
            dem[0] += 1                 # viec tra ve NGAY, y nhu VIEC_TRAIN

        w = E.AccWorker("u", _Cli(), _lam)
        w.start()
        try:
            w.giao(E.VIEC_TRAIN)
            time.sleep(giay)
        finally:
            w.stop()
        return dem[0]

    def test_viec_tra_ve_ngay_KHONG_duoc_quay_nong(self):
        n = self._dem_vong(giay=1.2)
        self.assertLessEqual(n, 4, "vong NONG: %d vong trong 1,2 giay -> an sach CPU, GUI treo" % n)

    def test_van_lam_viec_chu_khong_dung_han(self):
        self.assertGreaterEqual(self._dem_vong(giay=1.2), 1, "worker khong lam gi ca")

    def test_LENH_MOI_van_day_duoc_ngay_khong_phai_cho_het_nhip(self):
        """Ngu bu KHONG duoc lam lenh moi phai cho: `_huy.wait()` chu khong phai `time.sleep()`."""
        vet = []

        def _lam(_c, viec, _con):
            vet.append(viec)

        w = E.AccWorker("u", _Cli(), _lam)
        w.start()
        try:
            w.giao(E.VIEC_TRAIN)
            for _ in range(100):
                if vet:
                    break
                time.sleep(0.01)
            t0 = time.time()
            w.giao(E.VIEC_DOI_KENH)      # lenh moi ngay giua luc worker dang ngu bu
            for _ in range(200):
                if E.VIEC_DOI_KENH in vet:
                    break
                time.sleep(0.01)
            self.assertIn(E.VIEC_DOI_KENH, vet, "lenh moi khong toi duoc")
            self.assertLess(time.time() - t0, 0.9,
                            "phai day day ngay, khong bat lenh moi cho het nhip")
        finally:
            w.stop()


class TestLenhMoiCAT_NGANG_viec_dang_lam(unittest.TestCase):
    """Day la ca khac biet CHINH so voi engine cu: lenh moi khong cho acc "nghe thay", no CAT NGANG.

    Party 11 (15/09) chet dung o cho nay: `luumuoi` dang ket trong vong cho loi moi, lenh gom map
    ra deu 3 phut/lan suot 22 phut ma no khong he biet.
    """

    def test_dang_di_duong_ma_co_lenh_moi_thi_NHA_RA(self):
        xong = threading.Event()
        vet = []

        def _lam(_c, viec, con_lam):
            vet.append(viec)
            while con_lam():
                time.sleep(0.01)
            xong.set()

        w = E.AccWorker("m1", _Cli(), _lam)
        w.start()
        try:
            w.giao(E.VIEC_VE_MAP)
            for _ in range(200):
                if vet:
                    break
                time.sleep(0.01)
            w.giao(E.VIEC_DOI_KENH)
            self.assertTrue(xong.wait(3), "viec cu KHONG nha ra -> y het benh cua engine cu")
        finally:
            w.stop()

    def test_abort_duoc_truyen_xuong_ham_client(self):
        """`abort=` la duong huy co san trong client.py - phai dung no, khong duoc bo trong."""
        thay = {}

        class _C(_Cli):
            def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
                thay["abort"] = abort
                return True

        E.thi_hanh(_C(map_id=23011), E.VIEC_VE_MAP, lambda: True, dich=23851)
        self.assertIsNotNone(thay.get("abort"), "khong truyen abort -> viec chan khong huy duoc")
        self.assertFalse(thay["abort"](), "con_lam=True thi abort phai False")


if __name__ == "__main__":
    unittest.main()
