"""NGOAI GIO EVENT phai chan TRUOC khi di vao map event, khong phai sau.

User 09/09: "may xem cac party 40npc, ngoai time event roi ma log in vao thay van co log ko vao dc
map event, het event roi thi vao map event lam lon gi".

Hai cua "ngoai gio" (40NPC va loan dau) TUNG nam DUOI ca doan `go_to_event`. Acc login ngoai gio
van di het duong vao map event - cong su kien da dong nen khong bao gio vao duoc - roi vong ngoai
goi lai ham do mai.

Do tren party.log 09/09, event 40NPC dong luc 22:00:
    22:31:37 [xGAx] (LEADER) chua vao duoc map event 10991 (dang o 12003) -> thu lai (lan 1/5)
    ... dem tu 22:30 tro di: 3372 dong ...
`12003` chinh la map DOI THUONG - acc da dung o cho no can den, chi thieu moi viec ngung di vao
map event.

Ca thu hai, party 53 (`nhi_kieu` = 2K): 276 lan thu vao map 12922 tu 22:00 den 23:20 - TAM MUOI
PHUT. 2K KHONG khai bao `lich` trong events.json nen khong co cua ngoai gio nao ca; tran
`EV_VAO_HONG_TOI_DA` la luoi do cho truong hop do, KHONG thay cho viec khai bao lich.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

with mock.patch.object(sys, "argv", ["run_party_digioi.py"]):
    import run_party_digioi as R


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestThuTuChanTruoc(unittest.TestCase):
    def setUp(self):
        self.src = _src()
        self.i_vao = self.src.find("if c.go_to_event(ev):")
        self.assertGreater(self.i_vao, 0)

    def test_cua_40NPC_ngoai_gio_dung_TRUOC_go_to_event(self):
        i = self.src.find("40NPC NGOAI GIO event -> huy party")
        self.assertGreater(i, 0)
        self.assertLess(i, self.i_vao,
                        "cua ngoai gio nam duoi -> acc van di het duong vao map event (3372 dong)")

    def test_cua_LOAN_DAU_ngoai_gio_dung_TRUOC_go_to_event(self):
        i = self.src.find("LOAN DAU ngoai gio event -> ra khoi map")
        self.assertGreater(i, 0)
        self.assertLess(i, self.i_vao)

    def test_cua_ngoai_gio_THOAT_GAME_chu_khong_chay_tiep(self):
        for _moc in ("40NPC NGOAI GIO event -> huy party", "LOAN DAU ngoai gio event -> ra khoi map"):
            i = self.src.find(_moc)
            khoi = self.src[i:i + 900]
            self.assertIn("c.close(); return", khoi, _moc)


class TestTranThuLai(unittest.TestCase):
    """Event KHONG khai bao lich (2K) - luoi do cuoi cung de khong lap vo han."""

    def setUp(self):
        self.src = _src()

    def test_co_tran_va_tran_nho(self):
        self.assertTrue(hasattr(R, "EV_VAO_HONG_TOI_DA"))
        self.assertLessEqual(R.EV_VAO_HONG_TOI_DA, 5,
                             "tran cao qua thi van dot hang chuc phut moi dung")

    def test_vao_duoc_thi_XOA_bo_dem(self):
        """Truc trac thoang qua giua gio event khong duoc cong don thanh 'bo cuoc'."""
        i = self.src.find("if _vao_ok:")
        self.assertGreater(i, 0)
        self.assertIn("c._ev_vao_hong = 0", self.src[i:i + 200])

    def test_qua_tran_thi_THOAT_GAME(self):
        i = self.src.find("if c._ev_vao_hong >= EV_VAO_HONG_TOI_DA:")
        self.assertGreater(i, 0)
        self.assertIn("c.close(); return", self.src[i:i + 800])

    def test_bo_dem_nam_tren_CLIENT_khong_phai_bien_vong(self):
        """Vong ngoai goi lai ham -> bien cuc bo reset moi lan, dem khong bao gio len."""
        i = self.src.find("c._ev_vao_hong = int(getattr(c, \"_ev_vao_hong\", 0) or 0) + 1")
        self.assertGreater(i, 0)


class TestGuiKhongTuGanEventDauDanhSach(unittest.TestCase):
    """Party moi bat mode event, chua dong vao o Event -> KHONG duoc thanh event dau danh sach.

    Ca that: party 53 thanh `nhi_kieu` (2K) trong khi 52 party kia deu `npc_40`, roi bot di vao
    map 2K va thu vao 276 lan.
    """

    def setUp(self):
        with io.open(os.path.join(ROOT, "gui.py"), encoding="utf-8") as fh:
            self.gui = fh.read()

    def test_khong_con_fallback_index_0_am_tham(self):
        i = self.gui.find('cur = self._preset.get("event_key")')
        self.assertGreater(i, 0)
        khoi = self.gui[i:i + 700]
        self.assertNotIn("if k == cur), 0)", khoi,
                         "khong khop key -> lang le lay event dau danh sach")
        self.assertIn("_event_key_pho_bien()", khoi)

    def test_ham_pho_bien_dem_theo_cac_party_khac(self):
        i = self.gui.find("def _event_key_pho_bien():")
        self.assertGreater(i, 0)
        khoi = self.gui[i:i + 900]
        self.assertIn("PARTY_CONFIG", khoi)
        self.assertIn("event_key", khoi)

    def test_ham_pho_bien_chay_dung(self):
        """Doc lap voi Tk: lay than ham ra chay tren PARTY_CONFIG gia."""
        i = self.gui.find("def _event_key_pho_bien():")
        j = self.gui.find("self._event_key_pho_bien = _event_key_pho_bien", i)
        than = self.gui[i:j]
        than = re.sub(r"^        ", "", than, flags=re.M)   # bo thut le cua closure

        class _Cfg:
            PARTY_CONFIG = {0: {"mode": "event", "event_key": "npc_40"},
                            1: {"mode": "event", "event_key": "npc_40"},
                            2: {"mode": "train"},
                            3: {"mode": "event", "event_key": "nhi_kieu"}}

        ns = {"config": _Cfg}
        exec(compile(than, "<gui>", "exec"), ns)
        self.assertEqual(ns["_event_key_pho_bien"](), "npc_40")

    def test_khong_co_party_event_nao_thi_tra_None(self):
        i = self.gui.find("def _event_key_pho_bien():")
        j = self.gui.find("self._event_key_pho_bien = _event_key_pho_bien", i)
        than = re.sub(r"^        ", "", self.gui[i:j], flags=re.M)

        class _Cfg:
            PARTY_CONFIG = {0: {"mode": "train"}}

        ns = {"config": _Cfg}
        exec(compile(than, "<gui>", "exec"), ns)
        self.assertIsNone(ns["_event_key_pho_bien"]())


if __name__ == "__main__":
    unittest.main()
