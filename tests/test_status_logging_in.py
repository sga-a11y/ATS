"""Trang thai thu 3: DANG LOGIN (vang) - khong con chi co "chay" (xanh) va "tat" (xam).

Yeu cau user: acc bi server dut roi dang login lai truoc day van hien "CHAY" -> tuong no dang
danh. Phai co trang thai rieng, cham VANG, va cham party chi XANH khi TAT CA da login xong.

Kiem tra CA HAI ban:
  - PC : gui.py doc account_status()["logging_in"]
  - APK: BotForegroundService.kt map "logging_in" -> RunState.CONNECTING (mau vang co san)
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / "gui.py").read_text(encoding="utf-8")
RUNNER = (ROOT / "run_party_digioi.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "android/app/src/main/java/com/tsbot/android/BotForegroundService.kt").read_text(
    encoding="utf-8")
THEME = (ROOT / "android/app/src/main/java/com/tsbot/android/Theme.kt").read_text(encoding="utf-8")
UI = (ROOT / "android/app/src/main/java/com/tsbot/android/MainActivity.kt").read_text(
    encoding="utf-8")


class TestStatusLoggingIn(unittest.TestCase):
    def test_account_status_bao_dang_login(self):
        """Thread con song ma CHUA vao world (thieu self_entity hoac map) = dang login."""
        self.assertIn('"logging_in": bool(running and (c.self_entity is None '
                      'or c.current_map is None))', RUNNER)
        # acc co thread nhung CHUA co client (vua dut, chua tao lai) cung phai la dang login
        self.assertIn('return {"running": running, "logging_in": running,', RUNNER)
        self.assertIn('"state": "logging_in" if running else "stopped"', RUNNER)

    def test_pc_hien_nhan_va_mau_rieng(self):
        self.assertIn('tree.tag_configure("login", foreground="#b8860b")', GUI)
        self.assertIn('"● ĐANG LOGIN" if _dang_login', GUI)
        self.assertIn('tag = ("login" if _dang_login else', GUI)

    # Hai bai duoi neo theo Y NGHIA (dieu kien XANH), khong neo dang chu cua ca bieu thuc: dieu
    # kien nay tung nam thang trong bieu thuc `p_dot = ...`, sau do tach ra bien `_du_acc`/`_g_du`
    # khi them cham CAM cho lech AGI. Luat khong doi, chi doi cho dat.
    def test_pc_cham_party_chi_XANH_khi_khong_con_ai_dang_login(self):
        self.assertIn("p_run >= p_total and p_total > 0 and p_login == 0", GUI)
        self.assertIn("self._dot_on if _du_acc", GUI)
        self.assertIn("p_login += 1", GUI)

    def test_pc_cham_NHOM_cung_theo_quy_tac_do(self):
        self.assertIn("gr >= gt and gt > 0 and gl == 0", GUI)
        self.assertIn("self._dot_on if _g_du", GUI)
        self.assertIn("group_login[gidx] = group_login.get(gidx, 0) + p_login", GUI)

    def test_apk_map_sang_CONNECTING_va_co_mau_vang(self):
        self.assertIn('val loggingIn = gBool("logging_in")', SERVICE)
        self.assertIn("state = if (loggingIn) RunState.CONNECTING", SERVICE)
        self.assertIn("RunState.CONNECTING -> StatusConnecting", THEME)
        self.assertIn('RunState.CONNECTING -> "Đang kết nối"', THEME)

    def test_apk_cham_party_chi_XANH_khi_tat_ca_RUNNING(self):
        """running == size moi xanh; acc dang CONNECTING thi running < size -> vang."""
        self.assertIn("running == enabledAccounts.size -> StatusRunning", UI)
        self.assertIn("running > 0 || connecting -> StatusConnecting", UI)


if __name__ == "__main__":
    unittest.main()
