"""Bao loi (documents/BAO_LOI.md): loc dung log cua party, 2 phien gan nhat, khong lot password."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import bug_report as br  # noqa: E402


def _moc(so_party, ngay, users):
    return "10:00:00 %s %s v1.1.test acc=[%s]\n" % (br.MOC_PHIEN % so_party, ngay, ", ".join(users))


class LocLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "party.log")

    def tearDown(self):
        self.tmp.cleanup()

    def _ghi(self, path, lines):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(lines)

    def _trich(self, pidx=3, nhan=("sga015",), mat_khau=(), **kw):
        return list(br.trich_log(self.log, pidx, set(nhan), mat_khau, **kw))

    def test_lay_2_phien_gan_nhat_cua_party(self):
        self._ghi(self.log, [
            _moc(4, "2026-10-05 08:00:00", ["sga015"]),
            "10:00:01 [party 4] PHIEN 1\n",
            _moc(4, "2026-10-06 08:00:00", ["sga015"]),
            "10:00:02 [party 4] PHIEN 2\n",
            _moc(14, "2026-10-07 08:00:00", ["khac"]),    # PARTY 14 khong duoc tinh la moc PARTY 4
            _moc(4, "2026-10-07 08:00:00", ["sga015"]),
            "10:00:03 [party 4] PHIEN 3\n",
        ])
        out = "".join(self._trich())
        self.assertNotIn("PHIEN 1", out)
        self.assertIn("PHIEN 2", out)
        self.assertIn("PHIEN 3", out)
        self.assertTrue(out.startswith("10:00:00 >>> PARTY 4 BAT DAU PHIEN MOI 2026-10-06"))

    def test_chi_mot_moc_thi_lay_tu_dau(self):
        self._ghi(self.log, ["09:00:00 [party 4] TRUOC MOC\n", _moc(4, "2026-10-07 08:00:00", ["a"]),
                             "10:00:01 [party 4] SAU MOC\n"])
        out = "".join(self._trich())
        self.assertIn("TRUOC MOC", out)
        self.assertIn("SAU MOC", out)

    def test_moc_nam_o_file_xoay_vong(self):
        self._ghi(self.log + ".2", [_moc(4, "2026-10-05 08:00:00", ["a"]), "10:00:01 [party 4] CU NHAT\n"])
        self._ghi(self.log + ".1", [_moc(4, "2026-10-06 08:00:00", ["a"]), "10:00:01 [party 4] FILE 1\n"])
        self._ghi(self.log, [_moc(4, "2026-10-07 08:00:00", ["a"]), "10:00:01 [party 4] HIEN TAI\n"])
        out = "".join(self._trich())
        self.assertNotIn("CU NHAT", out)
        self.assertIn("FILE 1", out)
        self.assertIn("HIEN TAI", out)

    def test_tran_byte_cat_phan_cu_va_bo_dong_do(self):
        self._ghi(self.log, ["10:00:01 [party 4] %s\n" % ("x" * 50) for _ in range(100)]
                  + ["10:00:02 [party 4] CUOI\n"])
        out = self._trich(tran=200)
        self.assertTrue(out)
        self.assertIn("CUOI", out[-1])
        self.assertTrue(all(line.startswith("10:00:0") for line in out))

    def test_chi_giu_dong_cua_party(self):
        self._ghi(self.log, [
            _moc(4, "2026-10-07 08:00:00", ["sga015"]),
            "10:00:01 [sga015] login\n",
            "10:00:02 [sga015] NHAN LOG -> 'dieusau'\n",
            "10:00:03 [dieusau] BATTLE SEND\n",
            "10:00:04 [dieusau] [BATTLE g=5] BO goi KET TRAN\n",
            "10:00:05 [P4 BATTLE g=5 t=1] HIT\n",
            "10:00:06 [party 4] ENGINE: sga015 -> train\n",
            "10:00:07 >>> PARTY 4: thanh xuat phat\n",
            "10:00:08 [party 5] KHAC\n",
            "10:00:09 [P5 BATTLE g=1] KHAC\n",
            "10:00:10 [nguoikhac] KHAC\n",
            "10:00:11 >>> PARTY 5: KHAC\n",
            "10:00:12 >>> START TAT CA: he thong\n",
        ])
        out = "".join(self._trich())
        for giu in ("login", "NHAN LOG", "BATTLE SEND", "BO goi", "HIT", "ENGINE", "thanh xuat phat",
                    "he thong"):
            self.assertIn(giu, out)
        self.assertNotIn("KHAC", out)

    def test_traceback_di_theo_dong_tren(self):
        self._ghi(self.log, [
            "10:00:01 [sga015] LOI\n", "Traceback (most recent call last):\n", "  File x\n",
            "10:00:02 [khac] LOI KHAC\n", "Traceback KHAC\n",
        ])
        out = "".join(self._trich())
        self.assertIn("  File x", out)
        self.assertNotIn("KHAC", out)

    def test_password_lot_vao_log_bi_che(self):
        self._ghi(self.log, ["10:00:01 [sga015] dang nhap bang matkhau123 xong\n"])
        out = "".join(self._trich(mat_khau=("matkhau123",)))
        self.assertNotIn("matkhau123", out)
        self.assertIn("***", out)

    def test_khong_co_log(self):
        self.assertEqual(self._trich(), [])


class Config(unittest.TestCase):
    def _cfg(self):
        return types.SimpleNamespace(
            PARTIES=[], CHANNEL=4, PARTY_LEADERS=["chihao"], PARTY_LEADERS_BY_IDX={0: ["nasau"]},
            PARTY_CONFIG={0: {"mode": "train", "server": "trieu_van", "buy_hp": True}},
            ACCOUNT_HEAL={"sga001": {"hp_char": 0.7}}, ACCOUNT_VANTIEU={"khac": {"on": False}},
        )

    def test_khong_gui_password_van_giu_username(self):
        snap = br.chup_config(0, [("sga001", "matkhau123", True, False), ("sga002", "pw2222", False, False)],
                              self._cfg())
        txt = json.dumps(snap, ensure_ascii=False)
        self.assertNotIn("matkhau123", txt)
        self.assertNotIn("pw2222", txt)
        self.assertEqual(snap["accounts"], ["sga001", "sga002"])
        self.assertEqual(snap["party_config"]["mode"], "train")
        self.assertEqual(snap["account_config"]["sga001"], {"heal": {"hp_char": 0.7}})
        self.assertEqual(snap["account_config"]["sga002"], {})
        self.assertEqual(snap["leaders_party"], ["nasau"])

    def test_bo_khoa_password_long_nhau(self):
        self.assertEqual(br.bo_mat_khau({"a": [{"u": "x", "p": "y", "Password": "z"}]}),
                         {"a": [{"u": "x"}]})


class TaoBaoLoi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "party.log")
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write(_moc(1, "2026-10-07 08:00:00", ["sga001"]) + "10:00:01 [sga001] chay\n")
        self.cfg = types.SimpleNamespace(PARTY_CONFIG={0: {"mode": "train"}})
        self.accounts = [("sga001", "matkhau123", True, False)]
        br._lan_gui_cuoi = 0.0
        self.da_gui = []

    def tearDown(self):
        br._lan_gui_cuoi = 0.0
        self.tmp.cleanup()

    def _gui(self, zip_path, caption, bot):
        with zipfile.ZipFile(zip_path) as z:
            self.da_gui.append((sorted(z.namelist()), z.read("party.log").decode(), caption, bot))

    def _tao(self, mo_ta="party dung im khong danh", **kw):
        kw.setdefault("gui", self._gui)
        kw.setdefault("bot", {"token": "t", "chat_id": "1"})
        return br.tao_bao_loi(0, mo_ta, self.accounts, set(), self.cfg, self.log, self.tmp.name,
                              {"app_version": "1.1.app"}, **kw)

    def test_gui_thanh_cong(self):
        kq = self._tao()
        self.assertTrue(kq["ok"], kq)
        self.assertRegex(kq["ma"], r"^BL-\d{4}-[0-9A-F]{4}$")
        ten, log_txt, caption, _bot = self.da_gui[0]
        self.assertEqual(ten, ["config.json", "info.json", "party.log"])
        self.assertIn("chay", log_txt)
        self.assertIn(kq["ma"], caption)
        self.assertIn("party dung im", caption)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, br.THU_MUC_LUU, kq["ma"] + ".zip")))

    def test_mo_ta_qua_ngan(self):
        kq = self._tao("loi")
        self.assertFalse(kq["ok"])
        self.assertEqual(self.da_gui, [])

    def test_chong_spam(self):
        self.assertTrue(self._tao()["ok"])
        kq = self._tao()
        self.assertFalse(kq["ok"])
        self.assertIn("chờ", kq["loi"])

    def test_gui_hong_thi_giu_zip_va_cho_gui_lai(self):
        def hong(*_a):
            raise RuntimeError("mat mang")
        kq = self._tao(gui=hong)
        self.assertFalse(kq["ok"])
        self.assertIn("mat mang", kq["loi"])
        self.assertTrue(os.path.isfile(kq["file"]))
        self.assertTrue(self._tao()["ok"])   # khong bi chan 2 phut sau lan hong

    def test_thieu_cau_hinh_bot_thi_giu_zip(self):
        kq = self._tao(bot=None)
        self.assertFalse(kq["ok"])
        self.assertIn(br.TEN_FILE_BOT, kq["loi"])
        self.assertTrue(os.path.isfile(kq["file"]))


class NhungBotLucBuild(unittest.TestCase):
    """build_product.write_bao_loi_bot: token vao TRONG ban build, thieu file thi xoa module cu."""

    def setUp(self):
        import build_product
        self.bp = build_product
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "bao_loi_bot.json")
        self.stage = os.path.join(self.tmp.name, "stage")
        os.makedirs(self.stage)
        self.apk = os.path.join(self.tmp.name, "apk_bao_loi_bot.py")

    def tearDown(self):
        self.tmp.cleanup()

    def _doc(self, path):
        import ast
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        return ast.literal_eval(tree.body[-1].value)

    def test_sinh_module_cho_exe_va_apk(self):
        with open(self.src, "w", encoding="utf-8") as fh:
            json.dump({"token": "123:GIA", "chat_id": "42"}, fh)
        self.bp.write_bao_loi_bot(self.stage, self.src, self.apk)
        for f in (os.path.join(self.stage, "_bao_loi_bot.py"), self.apk):
            self.assertEqual(self._doc(f), {"token": "123:GIA", "chat_id": "42"})

    def test_thieu_file_thi_xoa_module_cu(self):
        for f in (os.path.join(self.stage, "_bao_loi_bot.py"), self.apk):
            with open(f, "w", encoding="utf-8") as fh:
                fh.write("BOT = {'token': 'CU'}\n")
        self.bp.write_bao_loi_bot(self.stage, self.src, self.apk)
        self.assertFalse(os.path.exists(os.path.join(self.stage, "_bao_loi_bot.py")))
        self.assertFalse(os.path.exists(self.apk))

    def test_file_hong_thi_dung_build(self):
        with open(self.src, "w", encoding="utf-8") as fh:
            fh.write("{khong phai json")
        with self.assertRaises(SystemExit):
            self.bp.write_bao_loi_bot(self.stage, self.src, self.apk)


if __name__ == "__main__":
    unittest.main()
