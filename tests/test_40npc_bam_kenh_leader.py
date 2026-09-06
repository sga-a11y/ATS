"""40NPC lech kenh: DIEU PHOI xu ly, KHONG de member tu bam kenh leader.

Ca goc phai cu duoc - log 31/08 party 2 (map 40NPC 10991):
    20:36:01  40NPC dang battle co dong doi ROT -> RELOGIN cung ca party
    20:36:13-22  4 member vao lai TRUOC, tu ve kenh CU 39
    20:36:56  leader gamo vao lai SAU 40s, spawn kenh 10
    20:37:01  Kenh it nguoi MA DU CHO ca party (5): kenh 34 -> chuyen sang
    20:37:12  sync kenh: 1/5 acc da sang kenh 34, con lai CHUA sang: {...: 39, 39, 39, 39}
    20:38:02  sync kenh/map TIMEOUT 60s (1/5) -> thoat, moi/reform lai
=> mat ca van 40NPC.

Ban cu chua bang mot nhanh RIENG: member tu doc `st["channel"]` roi tu `switch_channel`. Nhanh do
la CO CHE THU HAI cung ra lenh doi kenh, song song voi `kenh_dich` cua dieu phoi -> vi pham L1
(documents/RULE_DIEU_PHOI.md: chi MOT cho duoc quyet). Hai cai cung ra lenh thi khong ai chiu
trach nhiem hau qua, ma hau qua o day la TAN DOI: server cam doi kenh khi dang trong doi
(`result=3`) nen doi kenh = phai roi doi truoc.

Da giet party 5 hai lan trong ngay 06/09:
    16:34:14  4 member: Doi kenh 2 THAT BAI: DANG TO DOI (result=3) -> roi party roi thu lai
    16:34:53  leader qua cong len 12929 MOT MINH
    17:16:26  [thbay] (member) 40NPC: leader chon kenh 2, minh dang o 1 -> BAM SANG kenh leader
    17:16:26  [thbay] -> roi party roi thu lai
    17:17:37  leader leo tiep 12929 -> 12931 -> 12932 -> 12934 MOT MINH

Gio CHI dieu phoi chot kenh. No chot kenh DONG NGUOI NHAT - tuc voi ca tren se chot 39 (cho 4
member dang dung) chu khong phai 34: leader di sang cho member, khong keo 4 dua di. Vua it di
chuyen hon, vua chac chan con cho.
"""
from __future__ import annotations

import io
import os
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


class _C:
    def __init__(self, channel, map_id=10991):
        self.running = True
        self.current_map = map_id
        self.current_channel = channel
        self._chan_switch_result = None
        self._chan_switch_target = None
        self._chan_switch_luc = 0.0


class TestKhongConNhanhMemberTuBamKenh(unittest.TestCase):
    def test_da_bo_nhanh_bam_kenh_leader(self):
        s = _src()
        self.assertNotIn("BAM SANG kenh leader chon", s, "co che thu hai ra lenh doi kenh -> L1")
        self.assertNotIn("_lan_bam_kenh_leader", s)

    def test_khong_con_doi_kenh_theo_st_channel(self):
        """`st["channel"]` la co cua vong bat tay cu - khong duoc dung lam lenh doi kenh nua."""
        s = _src()
        for d in s.splitlines():
            if "switch_channel(" in d and not d.lstrip().startswith("#"):
                self.assertNotIn('st["channel"]', d, d.strip())


class TestDieuPhoiXuLyCaGoc(unittest.TestCase):
    """Ca 31/08: 4 member kenh 39, leader kenh 34 -> phai hoi tu, khong duoc mat van."""

    PARTY = 0
    ACCS = ("lead", "m1", "m2", "m3", "m4")

    def setUp(self):
        self._pa = R.party_accounts
        R.party_accounts = lambda pidx: [(u, "p", False, False) for u in self.ACCS]
        self._cl = dict(R.account_clients)
        R.account_clients.clear()
        R._party_state.pop(self.PARTY, None)
        self.st = R._pstate(self.PARTY)
        self._pc = getattr(R.config, "PARTY_CONFIG", {})
        R.config.PARTY_CONFIG = {self.PARTY: {"mode": "event", "event_key": "40npc"}}

    def tearDown(self):
        R.party_accounts = self._pa
        R.account_clients.clear(); R.account_clients.update(self._cl)
        R._party_state.pop(self.PARTY, None)
        R.config.PARTY_CONFIG = self._pc

    def _song(self):
        for u, ch in (("lead", 34), ("m1", 39), ("m2", 39), ("m3", 39), ("m4", 39)):
            R.account_clients[u] = _C(ch)
        return [(u, R.account_clients[u]) for u in self.ACCS]

    def test_chot_ve_kenh_DONG_NGUOI_NHAT_chu_khong_theo_leader(self):
        song = self._song()
        self.assertEqual(R._dieu_phoi_chot_kenh(self.PARTY, self.st, song), 39,
                         "keo 4 member sang kenh leader = di chuyen nhieu hon va co the het cho")

    def test_leader_cung_phai_theo_lenh(self):
        """Leader khong duoc mien - no cung chi la mot acc thi hanh."""
        s = _src()
        i = s.find('_kd = st.get("kenh_dich")')
        self.assertGreater(i, 0)
        khoi = s[i:i + 700]
        self.assertNotIn("is_leader", khoi, "leader duoc mien = lai co hai luat")


class TestVanChanDoiKenhGiuaTran(unittest.TestCase):
    def test_khong_doi_kenh_khi_dang_danh(self):
        s = _src()
        i = s.find('_kd = st.get("kenh_dich")')
        self.assertIn("not c.in_combat()", s[i:i + 400])


if __name__ == "__main__":
    unittest.main()
