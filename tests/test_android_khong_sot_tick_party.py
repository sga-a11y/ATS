# -*- coding: utf-8 -*-
"""APK - KHONG DUOC SOT MOT TICK NAO trong chuoi: UI -> luu -> truyen sang Python.

Moi tick cua party phai di qua BON mat xich. Dut mat xich nao thi tick do "khong co tac dung", va
khong mot dau hieu gi:

    1. `Party` (data class)         - co truong
    2. `currentParty()`             - dung Party tu state cua dialog
    3. `PartyStore`                 - doc/ghi JSON (song qua lan mo lai app)
    4. `BotForegroundService`       - truyen sang `setup_party_runtime`

### Ca that 23/09 - "ap dung cho tat ca party" XOA SACH tick doi qua event

User: *"tick tu doi qua event -> chon ap dung cho tat ca cac party thi thay cac party bi mat tick
doi qua qua event du truoc do co tick roi"*.

Goc: co HAI CHO dung `Party` song song - `currentParty()` va mot khoi `Party(...)` RIENG trong nut
Luu. Khoi nut Luu co du ba truong event, `currentParty()` thi SOT ca ba:

    autoEventExchange   -> mac dinh false        <- mat tick
    eventExchangeItems  -> mac dinh emptyList()  <- mat luon danh sach qua
    eventExchangeSig    -> mac dinh ""

Ma `currentParty()` chinh la NGUON cua nut "Ap dung cho tat ca party"
(`onApplyAdvancedToAll(currentParty())` -> `copyAdvancedSettingsFrom`), nen bam mot cai la chep
gia tri MAC DINH do sang moi party khac. LUU thi khong sao (khoi rieng co du) - chi "ap dung cho
tat ca" mat, nen rat kho doc tu ngoai.

Da gop lai MOT CHO: nut Luu goi `currentParty().copy(name = name.trim())`.

`accounts` khong tinh: no do man hinh danh sach acc quan ly, khong phai tick cua dialog party.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AND = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "tsbot", "android")

BO_QUA = {"accounts"}


def _doc(ten):
    with io.open(os.path.join(AND, ten), encoding="utf-8") as fh:
        return fh.read()


def _fields_party():
    s = _doc("Party.kt")
    i = s.find("data class Party(")
    assert i > 0, "mat data class Party"
    than = s[i:s.find("\n)", i)]
    return [m.group(1) for m in re.finditer(r"^\s*val ([a-zA-Z0-9_]+):", than, re.M)]


def _gan_trong_currentParty():
    s = _doc("MainActivity.kt")
    i = s.find("fun currentParty(): Party = Party(")
    assert i > 0, "mat currentParty()"
    than = s[i:s.find("\n    )", i)]
    return set(re.findall(r"^\s+([a-zA-Z0-9_]+) = ", than, re.M))


def _dem(s, f):
    return len(re.findall(r"\b%s\b" % re.escape(f), s))


class TestKhongDutChuoi(unittest.TestCase):
    def setUp(self):
        self.fields = [f for f in _fields_party() if f not in BO_QUA]
        self.cp = _gan_trong_currentParty()
        self.store = _doc("PartyStore.kt")
        self.svc = _doc("BotForegroundService.kt")

    def test_co_field_de_kiem(self):
        self.assertGreater(len(self.fields), 40, "doc hut field cua Party -> test thanh vo dung")

    def test_currentParty_KHONG_SOT_field_nao(self):
        """Sot o day = "ap dung cho tat ca party" chep GIA TRI MAC DINH sang moi party."""
        thieu = [f for f in self.fields if f not in self.cp]
        self.assertEqual(thieu, [], "currentParty() sot: %s" % thieu)

    def test_moi_field_deu_duoc_LUU(self):
        thieu = [f for f in self.fields if _dem(self.store, f) == 0]
        self.assertEqual(thieu, [], "PartyStore khong doc/ghi: %s" % thieu)

    def test_moi_field_deu_duoc_TRUYEN_sang_python(self):
        thieu = [f for f in self.fields if _dem(self.svc, f) == 0]
        self.assertEqual(thieu, [], "khong truyen sang setup_party_runtime: %s" % thieu)


class TestMotChoDungParty(unittest.TestCase):
    """Hai cho dung `Party` song song la cach bug 23/09 sinh ra. Giu cho chi con MOT."""

    def setUp(self):
        self.ui = _doc("MainActivity.kt")

    def test_nut_Luu_goi_currentParty(self):
        self.assertIn("onSave(currentParty().copy(name = name.trim()))", self.ui,
                      "nut Luu lai dung Party rieng -> se lech voi currentParty()")

    def test_chi_co_MOT_cho_dung_Party_tu_state(self):
        """Dem so lan dung `Party(` co gan `name = ` ngay sau - do la cho dung Party tu state."""
        _code = "\n".join(l for l in self.ui.splitlines() if not l.strip().startswith("//"))
        _n = len(re.findall(r"Party\(\s*\n\s+name = ", _code))
        self.assertLessEqual(_n, 1, "co %d cho dung Party tu state - chep tay se lech" % _n)

    def test_nut_ap_dung_cho_tat_ca_lay_tu_currentParty(self):
        self.assertIn("onApplyAdvancedToAll(currentParty())", self.ui)


class TestBaTruongEventCoMat(unittest.TestCase):
    """Neo dich danh ba truong da mat - de neu ai do lai xoa chung thi do ngay, khong phai doc
    thong bao chung chung."""

    def setUp(self):
        self.cp = _gan_trong_currentParty()
        self.party = _doc("Party.kt")

    def test_currentParty_co_du_ba_truong_event(self):
        for f in ("autoEventExchange", "eventExchangeItems", "eventExchangeSig"):
            self.assertIn(f, self.cp, "currentParty() sot %s -> ap dung cho tat ca se xoa tick" % f)

    def test_copyAdvancedSettingsFrom_van_chep_ba_truong_do(self):
        i = self.party.find("fun Party.copyAdvancedSettingsFrom")
        than = self.party[i:self.party.find("\n)", i)]
        for f in ("autoEventExchange", "eventExchangeItems", "eventExchangeSig"):
            self.assertIn("%s = source.%s" % (f, f), than)


if __name__ == "__main__":
    unittest.main()
