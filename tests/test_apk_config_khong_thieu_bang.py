"""CONG CHAN: config.py ban APK khong duoc THIEU bang data ma code dung chung co doc.

BUG THAT (2026-08-22): client.py doc `config.PET_SPECIAL_SKILL` o 3 cho, nhung config.py ban APK
KHONG he dinh nghia no -> `getattr(config, "PET_SPECIAL_SKILL", {})` tra RONG -> tren APK dac ky
pet KHONG BAO GIO dung duoc (ca trong combat lan dialog skill), ma khong co loi nao bao.
Ra ra thi thieu ca DONATE_MATERIALS va JIUGONGGE - 3 tinh nang chet am tham.

VI SAO CONG SYNC KHONG BAT: config.py KHONG nam trong SHARED cua tools/sync_apk_python.py (PC doc
file dia, APK doc asset qua _read_asset) nen moi ban mot bang loader CHEP TAY. Dung bai hoc trong
CLAUDE.md: "du lieu dung chung PC/APK thi cho nao chep tay la cho do se lech, chi la som hay muon".
Asset thi van duoc dong goi day du (SHARED_ASSETS co phu) - chi thieu HAM NAP.

Test nay bat: moi ten HOA ma bot/client.py hoac bot/combat.py doc qua `config.X` deu phai co o CA
HAI ban config.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PC_CFG = ROOT / "bot" / "config.py"
APK_CFG = ROOT / "android/app/src/main/python/train_bot/config.py"
DUNG_CHUNG = (ROOT / "bot" / "client.py", ROOT / "bot" / "combat.py")

# Ten CHI co o PC theo THIET KE (duong dan file tren dia, thu muc app... APK khong dung).
# Them vao day thi phai ghi RO LY DO, dung dung de lam im test.
CHI_PC = {
    "TRAIN_MAPS_PATH",      # duong dan file tren dia; APK co ban rieng tro vao filesDir
}


def ten_hoa(path):
    out = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    out.add(t.id)
    return out


class TestApkConfigKhongThieuBang(unittest.TestCase):
    def test_moi_bang_code_dung_chung_DOC_deu_co_o_ca_2_ban_config(self):
        pc, apk = ten_hoa(PC_CFG), ten_hoa(APK_CFG)
        src = "\n".join(p.read_text(encoding="utf-8") for p in DUNG_CHUNG)

        thieu = sorted(
            name for name in (pc - apk - CHI_PC)
            if re.search(r"config\.%s\b" % name, src)
            or re.search(r'getattr\(config,\s*"%s"' % name, src)
        )
        self.assertEqual(thieu, [], (
            "config.py ban APK THIEU %d bang ma code dung chung co doc: %s\n"
            "-> tren APK cac tinh nang do CHET AM THAM (getattr tra rong, khong loi nao bao).\n"
            "Them ham nap dung _read_asset vao android/.../train_bot/config.py."
            % (len(thieu), thieu)))

    def test_ba_bang_tung_thieu_gio_phai_co(self):
        """Chot cung 3 cai da tung thieu, de khong ai xoa lai."""
        apk = ten_hoa(APK_CFG)
        for name in ("PET_SPECIAL_SKILL", "DONATE_MATERIALS", "JIUGONGGE"):
            self.assertIn(name, apk, "config.py APK lai thieu %s" % name)

    def test_asset_cua_3_bang_do_thuc_su_duoc_dong_goi(self):
        """Co ham nap ma thieu asset thi cung chet am tham y het."""
        assets = ROOT / "android/app/src/main/assets/train_bot_data"
        for f in ("npc_special_skill.json", "donate_materials.json", "jiugongge.json"):
            self.assertTrue((assets / f).is_file(), "thieu asset APK: %s" % f)

    def test_ban_APK_nap_dac_ky_ra_dung_du_lieu(self):
        """Chay THAT ham nap cua ban APK tren file asset that - khong chi kiem ten bien."""
        import json
        raw = json.loads((ROOT / "android/app/src/main/assets/train_bot_data"
                          / "npc_special_skill.json").read_text(encoding="utf-8"))
        bang = {int(k, 16): int(v) for k, v in (raw.get("skills") or {}).items()}
        self.assertGreater(len(bang), 100, "bang dac ky rong/qua it")
        self.assertEqual(bang.get(0xa06e), 21006, "Chu Du (0xa06e) phai co dac ky 21006")


if __name__ == "__main__":
    unittest.main()
