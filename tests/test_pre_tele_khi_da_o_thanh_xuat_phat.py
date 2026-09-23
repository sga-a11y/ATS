# -*- coding: utf-8 -*-
"""DA O DUNG THANH XUAT PHAT -> VAN PHAI TELE LAI de reset vi tri.

`follow_smart_route` ban cu:

    if self.current_map != route["city"]:
        self.pre_route_town_hop()
        go_to_town(route["city"], route["flag"])
    # <- dang dung o chinh thanh do thi KHONG tele gi ca, di bo THANG tu toa do hien tai

Toa do hien tai co the la mot O KHONG DI DUOC (bot chay nham vao do truoc day). Luc do acc ket
VINH VIEN: lap party xong van khong nhuc nhich, vi moi buoc di deu xuat phat tu o ket.

User 23/09: *"login lai ma dang dung o thanh gan bai train thi dung yen do cho lap pt dung ko,
nhung t thay nhieu khi bot bi loi ngu gi do nen truoc do no chay ra diem ko di chuyen duoc cua map
do, nen lap party xong van ko di chuyen duoc"* -> *"lam cai pre tele la dc roi"*.

Teleport ve CHINH thanh dang dung dua nhan vat ve toa do spawn -> thoat o ket ma khong can biet o
nao chan (walkability nam trong `Ground.mmg`, bot chua co index per-map).

CHI KHI CHUA CO DOI: `go_to_town` phai `leave_party()` truoc (server cam tele khi con trong doi),
nen tele luc dang keo nhau ra bai la TU TAY xe party. Vua login thi roster rong - dung luc can.

`bot/client.py` la file DUNG CHUNG -> sua mot lan an ca PC lan APK (user nhac 23/09).
"""
from __future__ import annotations

import ast
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CLIENT = os.path.join(ROOT, "bot", "client.py")


def _than(ten):
    with io.open(CLIENT, encoding="utf-8") as fh:
        s = fh.read()
    i = s.find("def %s(" % ten)
    assert i > 0, "mat %s" % ten
    j = s.find("\n    def ", i + 10)
    return s[i:j if j > i else len(s)]


class TestTeleLaiKhiDaODungThanh(unittest.TestCase):
    def setUp(self):
        self.than = _than("follow_smart_route")

    def test_co_nhanh_DA_O_DUNG_THANH(self):
        self.assertIn("elif not self.party_members:", self.than,
                      "khong co nhanh xu ly 'dang dung o chinh thanh xuat phat'")

    def test_nhanh_do_VAN_TELE(self):
        # CAT THEO THAN NHANH, khong theo cua so ky tu co dinh: them comment la cua so truot ra
        # ngoai va test do ma luat khong he bi pha (da dinh nhieu lan).
        i = self.than.find("elif not self.party_members:")
        self.assertGreater(i, 0)
        j = self.than.find("deadline = time.time()", i)
        khuc = self.than[i:j if j > i else len(self.than)]
        self.assertIn("self.pre_route_town_hop()", khuc,
                      "tele THANG vao chinh thanh dang dung -> map khong doi -> go_to_town quay 150s")
        self.assertIn("self.go_to_town(route[\"city\"], route[\"flag\"])", khuc,
                      "khong tele lai -> khong reset duoc vi tri, acc ket o o khong di duoc")

    def test_CHI_khi_CHUA_CO_DOI(self):
        """`go_to_town` tu `leave_party()` truoc khi tele - tele luc dang co doi la xe party."""
        self.assertIn("not self.party_members", self.than)

    def test_VAN_GIU_nhanh_cu(self):
        """Dang o map KHAC thi van pre-tele trung gian roi moi ve thanh xuat phat."""
        self.assertIn('if self.current_map != route["city"]:', self.than)
        i = self.than.find('if self.current_map != route["city"]:')
        self.assertIn("self.pre_route_town_hop()", self.than[i:i + 300],
                      "mat buoc tele trung gian Trac Quan/Ng.Thanh")

    def test_tele_hong_thi_KHONG_bo_cuoc(self):
        """Ca cu (khong tele) van di duoc trong da so truong hop - tele hong thi cu di bo tiep,
        dung `return False` lam mat ca chuyen di."""
        i = self.than.find("elif not self.party_members:")
        khuc = self.than[i:i + 1400]
        self.assertNotIn("return False", khuc, "tele lai hong ma bo ca chuyen di")


class TestDuongREPLAY_van_pre_tele(unittest.TestCase):
    """`follow_route` (replay capture) LUON pre-tele + `go_to_town`, khong co cua bo qua. Giu
    nguyen - neu sau nay ai do them cua `if current_map != city` vao day thi no dinh dung benh."""

    def test_luon_pre_tele(self):
        than = _than("follow_route")
        self.assertIn("self.pre_route_town_hop()", than)
        self.assertNotIn('if self.current_map != city', than,
                         "them cua bo qua tele -> acc dung san o thanh se di bo tu o co the ket")


class TestDungChungPC_va_APK(unittest.TestCase):
    def test_nam_trong_file_SHARED(self):
        """`bot/client.py` phai nam trong danh sach file dong bo sang APK."""
        with io.open(os.path.join(ROOT, "tools", "sync_apk_python.py"), encoding="utf-8") as fh:
            s = fh.read()
        self.assertIn('"client.py"', s, "client.py khong con duoc sync sang APK")


class TestCuPhapConDung(unittest.TestCase):
    def test_client_py_parse_duoc(self):
        with io.open(CLIENT, encoding="utf-8") as fh:
            ast.parse(fh.read())


if __name__ == "__main__":
    unittest.main()
