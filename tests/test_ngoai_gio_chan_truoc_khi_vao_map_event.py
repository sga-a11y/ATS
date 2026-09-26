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
