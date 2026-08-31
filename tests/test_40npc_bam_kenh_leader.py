"""40NPC: MEMBER bam thang kenh LEADER dang dung - khong cho "leader goi".

`st["invited"]` chi co nghia "leader BAT DAU moi", KHONG phai "minh DA vao doi". Member thoat vong
cho ngay khi co co do roi vao thang nhanh dung yen -> tu do khong con cho nao doc kenh nua. Leader
doi kenh sau do thi khong ai nghe.

Log 31/08 party 2 (map 40NPC 10991):
    20:36:01  40NPC dang battle co dong doi ROT -> RELOGIN cung ca party
    20:36:13-22  4 member vao lai TRUOC, tu ve kenh CU 39
    20:36:56  leader gamo vao lai SAU 40s, spawn kenh 10
    20:37:01  Kenh it nguoi MA DU CHO ca party (5): kenh 34 -> chuyen sang
    20:37:12  sync kenh: 1/5 acc da sang kenh 34, con lai CHUA sang: {...: 39, 39, 39, 39}
    20:38:02  sync kenh/map TIMEOUT 60s (1/5) -> thoat, moi/reform lai
    20:38:02  chua moi 4 member: 'lech kenh live 39!=34' x4
=> mat ca van 40NPC.

Leader va member CUNG MOT TIEN TRINH -> doc thang `current_channel` cua leader, khong can goi nao.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestBamKenhLeader(unittest.TestCase):
    def setUp(self):
        s = _src()
        i = s.find("if event_party_mode and has_leader and not is_leader:")
        self.assertGreater(i, 0, "khong co nhanh bam kenh leader cho 40NPC")
        self.khoi = s[i:i + 1600]
        self.than = re.sub(r"#.*", "", self.khoi)
        self.src = s

    def test_bam_theo_kenh_leader_DA_CHON(self):
        """KHONG bam theo cho leader dang dung: kenh do co the het cho cho 4 dua con lai, nen
        leader VAN phai chon kenh - so no chot (`st["channel"]`) moi la dich."""
        self.assertIn('_ch_chon = st.get("channel")', self.than)
        self.assertNotIn('getattr(_lc, "current_channel"', self.than,
                         "bam theo cho leader dang dung -> kenh do co the day, ca party ket ngoai")

    def test_CHI_ap_dung_cho_40NPC(self):
        """Map train thuong da co luong dong bo rieng - ep them o day la pha ngang."""
        self.assertIn("event_party_mode and has_leader and not is_leader", self.than)

    def test_KHONG_doi_kenh_giua_tran(self):
        self.assertIn("not c.in_combat(", self.than)

    def test_co_RATE_LIMIT(self):
        self.assertIn("_lan_bam_kenh_leader", self.than)
        self.assertIn("_lan_bam_kenh_leader = 0.0", self.src, "chua khoi tao -> NameError vong dau")

    def test_loi_khong_lam_sap_vong_keepalive(self):
        self.assertIn("except Exception as e:", self.than)


if __name__ == "__main__":
    unittest.main()
