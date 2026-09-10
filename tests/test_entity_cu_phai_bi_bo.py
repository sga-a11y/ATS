"""ENTITY DOI MOI LAN LOGIN -> phai bo entity CU, khong leader moi vao nguoi da chet.

`_PARTY_ENTITIES` truoc day chi duoc THEM, khong bao gio xoa. Moi lan mot acc relogin, leader lai co
them mot entity CHET trong danh sach moi. No moi mai vao cai entity do, server khong he thay ai nhu
vay quanh no, va doi khong bao gio du.

Ca that 07/09 party 3 (16:46 -> 16:54): dieu phoi ra lenh lap lai party moi 2 phut ma vo ich, vi
loi moi ban vao khoang khong:

    [nanam] (LEADER) moi 1 member theo entity (live dung map/kenh): ['4ef7d7f8']
    [nanam] (LEADER) moi 1 nguoi ma SERVER CHUA HE cho thay ho quanh minh:
            ['4ef7d7f8:server CHUA HE bao thay nguoi nay quanh minh (chua co 0x03)']
    [party 3] DIEU PHOI: ca party da chung kenh 4 nhung DOI chua du
              (sga005=3 sga007=0 sga008=3 sga009=3 sga010=3) -> LAP LAI PARTY

`4ef7d7f8` la entity tu 12:34 cua mot phien truoc; sga007 (baybay) da relogin luc 16:44 va mang
entity khac. Roster cua no dung `0` suot 8 phut.

Nhan dien "cung mot acc" bang `_username` - khoa ON DINH qua cac lan login (entity thi khong).
"""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bot.client as CL   # noqa: E402


class _C:
    def __init__(self, u):
        self._username = u
        self._label = u


class TestBoEntityCu(unittest.TestCase):
    PIDX = 9911

    def setUp(self):
        for d in (CL._PARTY_ENTITIES, CL._PARTY_CLIENTS, CL._PARTY_JOINED):
            d.pop(self.PIDX, None)

    tearDown = setUp

    def _dk(self, u, ent, client=None):
        c = client or _C(u)
        CL._register_party_entity(self.PIDX, ent)
        CL._register_party_client(self.PIDX, ent, c)
        return c

    def test_relogin_thi_entity_cu_bi_bo(self):
        c = _C("sga007")
        self._dk("sga007", b"CU" * 4, c)
        self._dk("sga007", b"MOI" + b"x" * 5, c)
        ents = CL._PARTY_ENTITIES[self.PIDX]
        self.assertNotIn(b"CU" * 4, ents, "leader se moi vao entity chet")
        self.assertIn(b"MOI" + b"x" * 5, ents)

    def test_nhan_dien_qua_USERNAME_khong_can_cung_object(self):
        """Relogin tao client MOI - khong the so sanh bang `is`."""
        self._dk("sga007", b"CU" * 4)
        self._dk("sga007", b"MOI" + b"x" * 5)     # client khac han
        self.assertNotIn(b"CU" * 4, CL._PARTY_ENTITIES[self.PIDX])

    def test_KHONG_dung_vao_acc_khac(self):
        self._dk("sga005", b"A" * 8)
        self._dk("sga007", b"B" * 8)
        self._dk("sga007", b"C" * 8)
        ents = CL._PARTY_ENTITIES[self.PIDX]
        self.assertIn(b"A" * 8, ents, "da bo nham entity cua acc khac")
        self.assertNotIn(b"B" * 8, ents)
        self.assertIn(b"C" * 8, ents)

    def test_bo_ca_trong_so_dem_da_join(self):
        """Giu entity cu trong `_PARTY_JOINED` = bot tuong doi con du (L2d)."""
        c = _C("sga007")
        self._dk("sga007", b"CU" * 4, c)
        CL.mark_joined(self.PIDX, b"CU" * 4)
        self.assertEqual(CL.joined_member_count(self.PIDX), 1)
        self._dk("sga007", b"MOI" + b"x" * 5, c)
        self.assertEqual(CL.joined_member_count(self.PIDX), 0,
                         "so dem van giu entity chet -> bao 'du doi' oan")

    def test_dang_ky_lai_CUNG_entity_thi_khong_bo_gi(self):
        c = _C("sga007")
        self._dk("sga007", b"E" * 8, c)
        self._dk("sga007", b"E" * 8, c)
        self.assertIn(b"E" * 8, CL._PARTY_ENTITIES[self.PIDX])
        self.assertIn(b"E" * 8, CL._PARTY_CLIENTS[self.PIDX])

    def test_client_khong_co_username_thi_van_bo_theo_object(self):
        c = _C("x"); c._username = None
        self._dk(None, b"CU" * 4, c)
        self._dk(None, b"MOI" + b"x" * 5, c)
        self.assertNotIn(b"CU" * 4, CL._PARTY_ENTITIES[self.PIDX])


if __name__ == "__main__":
    unittest.main()
