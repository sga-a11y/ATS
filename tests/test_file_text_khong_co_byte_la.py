"""CONG CHAN: file text trong repo khong duoc chua byte dieu khien la (NUL, backspace...).

BUG THAT (2026-08-22): ghi muc van tieu vao KNOWLEDGE.md bang heredoc `python - <<'PY'`, day
escape bi nuot MOT TANG nen `\\0` thanh 3 byte NUL 0x00 THAT. Hau qua khong phai hong 1 dong ma
la: `grep` coi CA FILE la nhi phan va BO QUA TOAN BO, khong bao loi gi. Tra "thu cuoi" ra rong
-> ket luan nham KNOWLEDGE.md khong co muc do, trong khi no CO (muc Horse/Mount, 0x4f sub0100).

Tuc bay nay VO HIEU HOA chinh file kien thuc ma CLAUDE.md bat phai doc truoc khi boc goi.
Cung bay do tung lam `\\b` thanh backspace 0x08 trong tools/sync_apk_python.py (regex
"import bot\\b" khong bao gio khop -> cong chan build im lang cho qua).

Test nay quet cac file text va bat byte dieu khien ngoai tab/newline/CR.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DUOI = (".md", ".py", ".json", ".txt", ".gradle", ".kts", ".cfg", ".ini", ".yml", ".yaml")
BO_THU_MUC = {".git", "__pycache__", "build", "_lua_dec", "_lua_enc", "_work", "_stage",
              # _nk = cache Nuitka (no TU TAI bo bien dich MinGW ve). Thu vien chuan Python trong
              # do co 0x0c (dau ngat trang) HOP LE -> may nao da build 1 lan la test bao SAI 22 file
              # khong phai ma nguon cua minh. Da co trong .gitignore.
              "_nk",
              "aTSBot", "gui.dist", "gui.build", "gui.onefile-build", "node_modules",
              "scan_maps", ".gradle", ".idea", "venv", ".venv"}

# tab (09), newline (0a), CR (0d) la hop le
XAU = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Ngoai le CO CHU DICH - phai ghi ro ly do, dung dung de lam im test.
NGOAI_LE = {
    # SEP noi chuoi account giua Kotlin va Python, co ghi chu ro trong code.
    os.path.join("android", "app", "src", "main", "java", "com", "tsbot", "android",
                 "BotForegroundService.kt"): {0x01},
}


def _quet():
    loi = []
    for goc, thu_muc, files in os.walk(ROOT):
        thu_muc[:] = [d for d in thu_muc if d not in BO_THU_MUC and not d.startswith(".")]
        for ten in files:
            if not ten.endswith(DUOI):
                continue
            path = os.path.join(goc, ten)
            rel = os.path.relpath(path, ROOT)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            cho_phep = NGOAI_LE.get(rel, set())
            for m in XAU.finditer(data):
                b = data[m.start()]
                if b in cho_phep:
                    continue
                loi.append((rel, b, data[:m.start()].count(b"\n") + 1))
                break
    return loi


class TestFileTextKhongCoByteLa(unittest.TestCase):
    def test_khong_file_text_nao_co_byte_dieu_khien_la(self):
        loi = _quet()
        self.assertEqual(loi, [], "\n".join(
            ["File text co byte dieu khien la (grep se BO QUA ca file trong im lang):"] +
            ["   %s : byte 0x%02x tai dong %d" % x for x in loi] +
            ["Gan nhu chac chan do ghi file bang heredoc: \\0 -> NUL, \\b -> backspace.",
             "Dung Write/Edit tool, hoac chr(92)+'0' thay vi \\0. Xem CLAUDE.md."]))

    def test_KNOWLEDGE_md_grep_duoc(self):
        """File nay la file bi hong that -> chot rieng mot test cho no."""
        with open(os.path.join(ROOT, "KNOWLEDGE.md"), "rb") as fh:
            data = fh.read()
        self.assertNotIn(b"\x00", data, "KNOWLEDGE.md lai co byte NUL -> grep bo qua ca file")

    def test_cong_chan_thuc_su_bat_duoc(self):
        """Khong de test rong: tu dung mot mau co NUL va chac chan regex bat duoc."""
        self.assertTrue(XAU.search(b"abc\x00def"))
        self.assertTrue(XAU.search(b"abc\x08def"))
        self.assertIsNone(XAU.search(b"abc\tdef\r\nghi"))


if __name__ == "__main__":
    unittest.main()
