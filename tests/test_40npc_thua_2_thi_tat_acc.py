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

    def test_chua_toi_22h_thi_KHONG_goi_doi_thuong(self):
        """Server chi cho doi thuong sau 22h -> goi luc nay chac chan khong an. KHONG mat thuong:
        chay lai bot sau 22h thi no nhan (user xac nhan 31/08)."""
        i = self.src.find("if consec_loss >= 2 and not past_window:")
        khoi = self.src[i:i + 900]
        self.assertIn("client._npc40_bo_thuong = True", khoi)
        self.assertIn("in_event_window()", khoi, "khong phan biet truoc/sau 22h")
        s2 = _rpd()
        j = s2.find('getattr(c, "_npc40_bo_thuong", False)')
        self.assertGreater(j, 0, "coordinator van goi doi thuong khi chua toi 22h")
        self.assertIn("claim_40npc_reward(ev)", s2[j:j + 900], "sau 22h van phai doi thuong")

    def test_thua_2_thi_di_thang_toi_nhanh_XONG(self):
        i = self.src.find("if consec_loss >= 2 and not past_window:")
        self.assertGreater(i, 0)
        khoi = re.sub(r"#.*", "", self.src[i:i + 700])
        self.assertIn("past_window = True", khoi,
                      "khong dat co thi khong roi vao nhanh doi thuong")
        i_xong = self.src.find("if past_window:", i)
        self.assertGreater(i_xong, i, "nhanh XONG phai nam ngay sau")

    def test_VAN_bao_party_ngung_mo_battle(self):
        i = self.src.find("if consec_loss >= 2 and not past_window:")
        self.assertIn("on_loss()", self.src[i:i + 700])

    def test_van_dat_co_npc40_done(self):
        i = self.src.find("if past_window:")
        khoi = self.src[i:i + 600]
        self.assertIn("client._npc40_done = True", khoi)
        self.assertIn("_end_npc_dialog(client, sleep_fn)", khoi, "phai ket dialog truoc khi di")

    def test_log_noi_ro_LY_DO(self):
        """Het gio va thua 2 tran deu vao chung mot nhanh - khong noi ro thi doc log khong biet."""
        i = self.src.find("if past_window:")
        khoi = self.src[i:i + 600]
        self.assertIn("thua 2 tran lien tiep", khoi)
        self.assertIn("het gio event", khoi)

    def test_coordinator_VAN_tat_acc(self):
        s = _rpd()
        i = s.find('st["go_claim"].is_set():')
        self.assertGreater(i, 0)
        khoi = s[i:i + 1400]
        self.assertIn("claim_40npc_reward(ev)", khoi, "phai doi thuong truoc khi tat")
        self.assertIn("c.close(); break", khoi, "khong tat acc -> van dung yen nhu cu")


if __name__ == "__main__":
    unittest.main()
