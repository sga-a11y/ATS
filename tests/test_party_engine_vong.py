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
    def follow_smart_route(self, dest_map, safe, abort=None, flee=True):
        self.da_goi.append(("follow_smart_route", dest_map))
        self.current_map = dest_map
        return True

    def switch_channel(self, ch, *a, **k):
        self.da_goi.append(("switch_channel", ch))
        self.current_channel = ch
        return True

    def invite_train_party_participants(self, gap=1.0):
        self.da_goi.append(("invite", gap))
        return True

    def set_party_invite_ready(self, ready=True):
        self.da_goi.append(("invite_ready", ready))

    def combat_ready(self):
        self.da_goi.append(("combat_ready",))


def _engine(clients, can=2, map_dich=None, log=None):
    def _doc():
        return [(u, c, u == "l") for u, c in clients]
    return E.PartyEngine(40, _doc, can_bao_nhieu=can, map_dich=map_dich, log=log)


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
        """Giao lai viec giong het moi giay = lam viec dang chay bi huy lien tuc, acc khong bao gio
        di toi noi. `AccWorker.giao` phai tra False khi viec khong doi."""
        cl = [("l", _Cli(map_id=23851, members=2)), ("m1", _Cli(map_id=23011))]
        eng = _engine(cl)
        eng.start()
        try:
            eng.nhip()
            w = eng._workers["m1"]
            for _ in range(100):
                if w.viec_hien_tai() == E.VIEC_VE_MAP:
                    break
                time.sleep(0.01)
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

    def test_ve_map_dung_follow_smart_route(self):
        c = _Cli(map_id=23011)
        self.assertIn(("follow_smart_route", 23851), self._lam(E.VIEC_VE_MAP, c, 23851))

    def test_ve_map_KHONG_lam_gi_khi_da_dung_cho(self):
        c = _Cli(map_id=23851)
        self.assertEqual(self._lam(E.VIEC_VE_MAP, c, 23851), [])

    def test_doi_kenh_dung_switch_channel(self):
        c = _Cli(kenh=7)
        self.assertIn(("switch_channel", 1), self._lam(E.VIEC_DOI_KENH, c, 1))

    def test_LEADER_moi_con_member_chi_MO_CUA_NHAN(self):
        """Member tu moi ai la acc tu quyet (L1). No chi duoc mo cua nhan loi moi."""
        lead = _Cli()
        lead._pe_la_leader = True
        self.assertIn(("invite", 1.0), self._lam(E.VIEC_LAP_PARTY, lead))
        mem = _Cli()
        mem._pe_la_leader = False
        self.assertIn(("invite_ready", True), self._lam(E.VIEC_LAP_PARTY, mem))

    def test_viec_vat_thi_KHONG_DUNG_VAO(self):
        """User 14/09: "khi dang danh PB don va daily quest thi dieu phoi tam thoi ko quay ray"."""
        c = _Cli(vat=True)
        self.assertEqual(self._lam(E.VIEC_VIEC_VAT, c), [])

    def test_train_thi_tat_flee_va_bat_combat(self):
        c = _Cli()
        self._lam(E.VIEC_TRAIN, c)
        self.assertFalse(c.flee_mode)
        self.assertIn(("combat_ready",), c.da_goi)


class TestChoreGoiHamCO_THAT(unittest.TestCase):
    """Dat sai ten ham thi `getattr` tra None va viec do bi BO QUA AM THAM - khong loi, khong log.

    Dung kieu loi `_load_gamedata_items()` da can hai lan trong mot ngay (CLAUDE.md): thieu truong
    thi doc ra 0, khong ai biet, va bot vut sach hang tram trang bi. O day neu go sai ten thi acc
    lang le khong danh PB don / khong nhan van tieu suot ca ngay.
    """

    def test_moi_ten_ham_trong_CHORE_deu_ton_tai_that(self):
        from bot import client as C
        thieu = [ten for _co, ten in E.CHORE if not hasattr(C.GameClient, ten)]
        self.assertEqual(thieu, [], "ten ham khong co that -> viec bi bo qua AM THAM")

    def test_chore_phu_du_viec_hang_ngay(self):
        ten = {t for _c, t in E.CHORE}
        for _bat_buoc in ("do_daily_dungeon", "do_world_boss_all", "claim_daily_quests"):
            self.assertIn(_bat_buoc, ten, "thieu %s -> acc mat luot ca ngay" % _bat_buoc)

    def test_mot_viec_LOI_khong_lam_mat_viec_con_lai(self):
        """Truoc day ca chuoi nam trong MOT try -> hong mot cai la mat sach nhung cai sau."""
        goi = []

        class _C2(_Cli):
            def request_offline_exp(self, *a, **k):
                goi.append("offline")
                raise RuntimeError("no")

            def do_daily_dungeon(self, *a, **k):
                goi.append("dungeon")

            def claim_daily_quests(self, *a, **k):
                goi.append("daily")

        E.lam_viec_vat(_C2(), pcfg={}, log=None)
        self.assertIn("dungeon", goi, "viec dau no -> mat sach viec sau")
        self.assertIn("daily", goi)

    def test_co_TAT_trong_config_thi_KHONG_lam(self):
        goi = []

        class _C3(_Cli):
            def do_world_boss_all(self, *a, **k):
                goi.append("wb")

        E.lam_viec_vat(_C3(), pcfg={"auto_world_boss": False}, log=None)
        self.assertNotIn("wb", goi, "user tat ma bot van lam")

    def test_xong_thi_DANH_DAU_de_nhip_sau_thoi_giao(self):
        c = _Cli()
        del c._pe_xong_chore
        E.lam_viec_vat(c, pcfg={}, log=None)
        self.assertTrue(getattr(c, "_pe_xong_chore", False))

    def test_co_lenh_moi_thi_NHA_RA_giua_chung(self):
        """Lenh moi CAT NGANG - nhung lan sau phai lam tiep, khong duoc danh dau la xong."""
        c = _Cli()
        del c._pe_xong_chore
        self.assertFalse(E.lam_viec_vat(c, pcfg={}, log=None, con_lam=lambda: False))
        self.assertFalse(getattr(c, "_pe_xong_chore", False),
                         "bi cat ngang ma danh dau xong -> mat het viec vat ca ngay")


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

    def test_leader_goi_kich_ban_PB_co_san(self):
        goi = []

        class _C(_Cli):
            def do_team_dungeon(self, level):
                goi.append(int(level))
                return True

        E.thi_hanh(_C(), E.VIEC_PB_DOI, lambda: True, dich=80)
        self.assertEqual(goi, [80])

    def test_KHONG_dat_han_cho_cho_PB(self):
        """Engine cu tung co watchdog 180s va no keo CA 4 MEMBER ra relogin GIUA pho ban, pha nat
        luot PB. PB chay 10-20 phut la BINH THUONG."""
        s = io.open(os.path.join(ROOT, "bot", "party_engine.py"), encoding="utf-8").read()
        i = s.find("if viec == VIEC_PB_DOI:")
        khoi = s[i:i + 700]
        for _cam in ("timeout", "deadline", "time.time()"):
            self.assertNotIn(_cam, khoi, "dat han cho PB -> keo ca party ra giua pho ban")


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
