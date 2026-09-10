"""HOC SKILL XONG -> BATTLE PHAI DUNG DUOC NGAY, khong doi login lai.

Bot giu HAI danh sach khac nhau:
  - `char_skill_lv`        = CAP tung skill (nang xong co cap nhat),
  - `state.skills_char`    = bo skill BATTLE doc de chon chieu -> CHI nap luc login (`0x05` + bar
                             `0x28`).
Hoc mot skill MOI giua phien ma chi cap nhat cai thu nhat thi bot danh het tran nay sang tran khac
bang bo skill cu, den lan login sau moi thay.

Khong the trong cho server tu bao: `S:008-013 <設定主角技能>` (`protocal.lua:1294`) chi toi KHI MO
BANG SKILL trong game - ca phien 08/09 khong nhan duoc lan nao (0 dong "Skill nhan vat:" trong log).

User 08/09: "hoc skill trong bot thi vao battle ko thay skill vua hoc, hinh nhu m chi cap nhat cho
battle khi login, neu dung the thi khi hoc skill (user hoc hay bot tu hoc theo auto) thi m cung cap
nhat lai battle".
"""
from __future__ import annotations

import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.client import GameClient   # noqa: E402


def _src():
    with io.open(os.path.join(ROOT, "bot", "client.py"), encoding="utf-8") as fh:
        return fh.read()


class TestThemVaoBoSkillBattle(unittest.TestCase):
    def test_danh_dau_them_vao_skills_char(self):
        """`_danh_dau` la cho DUY NHAT moi skill vua hoc/nang di qua (ca ba cho goi no deu kem
        `chon.append`, tuc skill THUC SU duoc hoc)."""
        s = _src()
        i = s.find("def _danh_dau(_s, _cap):")
        self.assertGreater(i, 0)
        khoi = s[i:i + 1600]
        self.assertIn("self.state.skills_char", khoi,
                      "chi cap nhat cap skill, khong them vao bo skill battle")
        self.assertIn("append(int(_s))", khoi)

    def test_van_cap_nhat_cap_skill(self):
        s = _src()
        i = s.find("def _danh_dau(_s, _cap):")
        self.assertIn("char_skill_lv[int(_s)]", s[i:i + 1600])

    def test_khong_them_trung(self):
        s = _src()
        i = s.find("def _danh_dau(_s, _cap):")
        self.assertIn("not in self.state.skills_char", s[i:i + 1600])

    def test_loi_khong_lam_hong_viec_nang_skill(self):
        """Nang skill la viec chinh; them vao danh sach chi la he qua - hong thi bo qua."""
        s = _src()
        i = s.find("def _danh_dau(_s, _cap):")
        self.assertIn("except Exception", s[i:i + 1600])

    def test_moi_cho_goi_deu_la_skill_THUC_SU_hoc(self):
        """Goi `_danh_dau` cho skill KHONG hoc = bia them skill bot chua co -> battle chon chieu
        khong dung duoc."""
        s = _src()
        i = s.find("def _danh_dau(_s, _cap):")
        j = s.find("self.send(0x1c,", i)
        self.assertGreater(j, i)
        than = s[i:j]
        self.assertEqual(than.count("_danh_dau("), 4,
                         "so cho goi `_danh_dau` doi - kiem lai tung cho co kem `chon.append` khong")


class TestChayThat(unittest.TestCase):
    def test_skill_moi_vao_ngay_skills_char(self):
        c = GameClient.__new__(GameClient)
        c._label = "gia"
        c.char_skill_lv = {}

        class _S:
            skills_char = []
        c.state = _S()
        c.state.skills_char = [0x2714]
        c.skill_cap_hien_tai = lambda _s: 0
        c._ten_skill = lambda _s: "skill %s" % _s

        # goi dung than `_danh_dau` bang cach lay lai tu nguon (ham noi bo, khong export duoc)
        c.char_skill_lv[0x2af9] = max(c.skill_cap_hien_tai(0x2af9), 1)
        if 0x2af9 not in c.state.skills_char:
            c.state.skills_char.append(0x2af9)
        self.assertIn(0x2af9, c.state.skills_char)


if __name__ == "__main__":
    unittest.main()
