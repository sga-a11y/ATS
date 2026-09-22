# -*- coding: utf-8 -*-
"""LOI MOI PHONG PHO BAN la goi GUI MU -> phai IN DOI CHIEU truoc khi gui.

`0x2f 0800 [entity]` khong co goi tra loi nao. Entity sai thi goi roi vao hu khong, leader dung
cho du 40 giay roi bao `SERVER moi cong nhan 0/4 member`, va trong log KHONG CO GI de lan ra vi
sao - phia member cung im (member nhan duoc moi thi LUON in "Nhan moi PHO BAN ... da DONG Y").

Ca that 22/09 party 21 (19:56 -> 20:02, bay vong y het nhau):
    19:57:07 [dieusau] (LEADER) === PHO BAN TO DOI LV20: tao + moi 4 member ===
    19:57:53 [dieusau] (LEADER) lv20 SERVER moi cong nhan 0/4 member vao phong sau 40.2s
    ... 19:58:39 / 19:59:26 / 20:00:12 / 20:01:02 / 20:01:49 / 20:02:35 ...
    20:00:49 [party 21] ENGINE: 'pb_doi' giao lai 4680 lan lien tiep cho dieu906

Doi chieu doc THANG client cua tung acc trong party (L2 - ca party chung mot tien trinh), khong
bat acc bao cao.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _than_ham():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        s = fh.read()
    i = s.find("def _invite_team_dungeon_participants(")
    assert i > 0, "mat ham moi member vao phong pho ban"
    j = s.find("\n    def ", i + 10)
    return s[i:j]


class TestInDoiChieuTruocKhiGui(unittest.TestCase):
    def setUp(self):
        self.than = _than_ham()

    def test_CO_in_danh_sach_entity_sap_moi(self):
        self.assertIn("moi %d member theo entity", self.than,
                      "gui mu ma khong in gi -> lan sau lai khong biet vi sao 0/4")

    def test_doi_chieu_voi_client_LIVE_cua_party(self):
        """Entity chet = khong client nao dang mang no (acc relogin mang entity khac)."""
        self.assertIn("_PARTY_CLIENTS.get(self.party_idx)", self.than,
                      "khong doc client live thi khong biet entity con dung khong")
        self.assertIn("self_entity", self.than, "khong so entity LIVE cua acc do")

    def test_co_noi_acc_da_tat_chua(self):
        self.assertIn('"running"', self.than, "acc da tat ma van moi thi phai noi ra")

    def test_co_noi_SERVER_da_cho_thay_nguoi_do_chua(self):
        """`0x03 PlayerAppear` la bang chung server-side 'dang cung cho' (KNOWLEDGE.md muc 7)."""
        self.assertIn("da_thay_tan_mat(", self.than)

    def test_IN_TRUOC_khi_gui_goi(self):
        i_log = self.than.find("moi %d member theo entity")
        i_gui = self.than.find('self.send(0x2f, b"\\x08\\x00"')
        self.assertGreater(i_log, 0)
        self.assertGreater(i_gui, 0)
        self.assertLess(i_log, i_gui,
                        "in sau khi gui thi vong gui hong dau tien da troi mat ngu canh")

    def test_KHONG_bat_acc_bao_cao(self):
        """L2: doc thang client, khong qua bang cap party / co bao cao."""
        for cam in ("st[", "bao_cao", "report"):
            self.assertNotIn(cam, self.than, "dung bang bao cao: " + cam)

    def test_KHONG_doi_hanh_vi_gui(self):
        """Them log KHONG duoc dong vao viec gui - van gui DU tung entity mot, cach nhau `gap`."""
        self.assertIn('self.send(0x2f, b"\\x08\\x00" + bytes(entity))', self.than)
        self.assertIn("time.sleep(gap)", self.than)
        self.assertEqual(len(re.findall(r"self\.send\(0x2f, b\"\\x08\\x00\"", self.than)), 1,
                         "gui hai lan = member nhan hai loi moi")


if __name__ == "__main__":
    unittest.main()
