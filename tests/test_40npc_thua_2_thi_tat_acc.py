"""40NPC thua 2 tran lien tiep -> doi thuong roi TAT ACC, KHONG dung cho het gio.

Truoc day: thua 2 tran thi `_wait_until_after_window` giu acc dung yen trong map event cho toi
22h moi di doi thuong. Nhin tu ngoai, acc do "dang chay" ma khong lam gi - khong phan biet duoc
voi treo/ket (user 31/08: "gio dang cho dung yen tai cho thi t cha biet the nao ma lan").
Thua 2 tran roi thi ngoi them may tieng cung khong danh duoc nua.
"""
from __future__ import annotations

import io
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _npc40():
    with io.open(os.path.join(ROOT, "bot", "npc40.py"), encoding="utf-8") as fh:
        return fh.read()


def _rpd():
    with io.open(os.path.join(ROOT, "run_party_digioi.py"), encoding="utf-8") as fh:
        return fh.read()


class TestThua2ThiTatAcc(unittest.TestCase):
    def setUp(self):
        self.src = _npc40()

    def test_KHONG_con_vong_cho_het_gio(self):
        self.assertNotIn("def _wait_until_after_window(", self.src,
                         "con vong cho -> acc van dung yen hang tieng, khong biet song hay chet")
        self.assertNotIn("_wait_until_after_window(", self.src)

    def _ket_thuc(self):
        """Ba loi ra (het gio / thua 2 tran / thua sach) da gop vao chung ham `_ket_thuc` (02/09)."""
        i = self.src.find("def _ket_thuc(")
        self.assertGreater(i, 0, "khong con ham ket thuc chung")
        return self.src[i:self.src.find("\ndef ", i + 10)]

    def test_chua_toi_22h_thi_KHONG_goi_doi_thuong(self):
        """Server chi cho doi thuong sau 22h -> goi luc nay chac chan khong an. KHONG mat thuong:
        chay lai bot sau 22h thi no nhan (user xac nhan 31/08)."""
        khoi = self._ket_thuc()
        self.assertIn("client._npc40_bo_thuong = True", khoi)
        self.assertIn("in_event_window()", khoi, "khong phan biet truoc/sau 22h")
        s2 = _rpd()
        j = s2.find('getattr(c, "_npc40_bo_thuong", False)')
        self.assertGreater(j, 0, "coordinator van goi doi thuong khi chua toi 22h")
        self.assertIn("claim_40npc_reward(ev)", s2[j:j + 900], "sau 22h van phai doi thuong")

    def test_thua_2_thi_di_thang_toi_nhanh_XONG(self):
        """Thua 2 tran -> ket thuc NGAY, khong roi xuong doan hoi mau + mo tran tiep."""
        # Neo tu doan XU LY SAU KHI CO PROMPT (sau marker `thu_lai = 0`) - phia tren no la nhanh
        # thu lai khi mat prompt, cung co `_open_event_battle(` nhung khong lien quan.
        than = re.sub(r"#.*", "", self.src[self.src.find("thu_lai = 0     # co prompt"):])
        i = than.find("if consec_loss >= 2:")
        self.assertGreater(i, 0)
        self.assertIn("return _ket_thuc(", than[i:i + 200])
        self.assertLess(i, than.find("_open_event_battle("), "phai thoat truoc khi mo tran tiep")
        self.assertLess(i, than.find("before_repeat()"), "thua roi con hoi mau lam gi")

    def test_VAN_bao_party_ngung_mo_battle(self):
        self.assertIn("on_loss()", self._ket_thuc())

    def test_van_dat_co_npc40_done(self):
        khoi = self._ket_thuc()
        self.assertIn("client._npc40_done = True", khoi)
        self.assertIn("_end_npc_dialog(client, sleep_fn)", khoi, "phai ket dialog truoc khi di")

    def test_log_noi_ro_LY_DO(self):
        """Ba loi ra deu vao chung mot ham - khong noi ro thi doc log khong biet vi sao acc tat."""
        self.assertIn("ly_do", self._ket_thuc(), "log khong noi ly do")
        than = self.src[self.src.find("    consec_loss = 0"):]
        for ly_do in ("THUA 2 tran lien tiep", "het gio event (qua 22h)",
                      "thua sach (khong co prompt)", "khong vao lai duoc tran"):
            self.assertIn(ly_do, than)

    def test_coordinator_VAN_tat_acc(self):
        s = _rpd()
        i = s.find('st["go_claim"].is_set():')
        self.assertGreater(i, 0)
        khoi = s[i:i + 1400]
        self.assertIn("claim_40npc_reward(ev)", khoi, "phai doi thuong truoc khi tat")
        self.assertIn("c.close(); break", khoi, "khong tat acc -> van dung yen nhu cu")


if __name__ == "__main__":
    unittest.main()
