"""Sinh items_gamedata.json: ten + HP/SP hoi + co RESTRICT cua moi item.

Truong `restrict` (ItemData.lua:346 --[30] 限制) la BITMASK:
    0 co the vut | 1 vut la mat | 2 khong chuyen nhuong | 4 KHONG PHAI NGUYEN LIEU HOP
    8 KHONG THE BI HOP | 16 khong ban cho Npc | 32 khong gui ngan hang
Client loc item cho HOP VAT PHAM bang dung bit 4 (UICompound.lua:435):
    if bit.band(itemDatas[id].restrict, 4) ~= 0 then return false end
Nen bot phai dung cung dieu kien do, KHONG loc theo TEN (truoc day hardcode
_COMBINE_EXCLUDE = ("Huong Dung Ma Duoc", "Huong Dung Dai Duoc") -> sot "Bo Tay" va moi item
moi cua game).

Ghi them "restrict" vao MOI item co restrict != 0 (item binh thuong = 0 -> bo qua cho file gon).
Cac truong cu (name / hp / sp / battle) GIU NGUYEN de khong pha code dang doc file nay.

File .dat KHONG theo repo (gitignore) - copy tu client vao truoc khi chay.
Chay: python tools/crack_items_gamedata.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find          # noqa: E402
from crack_furnace_notify import read_items        # noqa: E402

OUT = os.path.join(ROOT, "items_gamedata.json")

# Mo ta item (ItemData.lua --[55] 說明) TACH RA FILE RIENG, KHONG nhap vao items_gamedata.json.
# Ly do: 25634 item deu co mo ta, tong 1.32 TRIEU ky tu -> nhet chung se day file tu 2.4MB len
# ~6.5MB, ma items_gamedata.json duoc MOI tien trinh party load het vao RAM (bot chay chuc party).
# Mo ta chi phuc vu dialog Tui do ben GUI -> de rieng, chi luc mo dialog moi doc.
OUT_DESC = os.path.join(ROOT, "items_desc.json")


def _set_tab_fields(rec, src):
    """Ghi `ft` (fitType) + `kd` (kind) - 2 truong DUY NHAT can de chia 4 tab tui do.

    Xem bot/bag_tabs.py: sao dung Item.ConditionEquip/Props/Material cua client. Da kiem tren
    ca 25668 item: 3 tab chia TRON VEN, khong mon nao thuoc 2 tab, khong mon nao lot ra ngoai.

    Bo qua gia tri 0 cho file gon (fitType=0 o 12934/25668 muc = khong phai trang bi). `kind`
    khong bao gio 0 nen luon ghi. Tong: 1.77MB -> 2.42MB.

    Item CHI co trong file ma KHONG co trong .dat (624 muc, them tu cac lan crack truoc) thi
    khong co 2 truong nay -> bag_tabs coi la "Vat pham", va van hien o tab "Tat ca".
    """
    for key, field in (("ft", "fitType"), ("kd", "kind"),
                      # bs = btnState: >0 moi hien nut "Su dung" (Item.CheckItemUseState,
                      #      Logic_Item.lua:3278). ==11 thi trong TRAN khong dung duoc.
                      ("bs", "btnState"),
                      # st = sort (ItemData --[45] 排序): THU TU SAP XEP trong tui do cua client.
                      #      Item.GetBagByCategory sap theo Item.Sort = (sort ASC, id ASC), KHONG
                      #      phai theo so o. Chay 1..254, khong co 0 -> muc nao cung duoc ghi.
                      ("st", "sort"),
                      # fc = furnaceCount: >0 moi hien nut "Phan giai" (Item.IsDismantle:2519).
                      ("fc", "furnaceCount"),
                      # --- CHI TIET TRANG BI (cho dialog Tui do ben gui.py) ---
                      # nl = needLv: cap toi thieu de mac.
                      ("nl", "needLv"),
                      # a1k/a1v, a2k/a2v = 2 dong chi so cong them. Ma chi so tra o
                      # Data_ItemData.lua GetAttributeName -> TextData_C.dat:
                      #   207 HP | 208 SP | 210 Atk | 211 Def | 212 Int | 214 Agi
                      #   217 Thuyen toc | 218 The chat (HPx) | 219 Nang luong (SPx)
                      ("a1k", "a1k"), ("a1v", "a1v"), ("a2k", "a2k"), ("a2v", "a2v"),
                      # el/elv = he + tri so he; su = bo do (suit).
                      ("el", "element"), ("elv", "elementValue"), ("su", "suitId"),
                      # sa = specialAbility (EItemUseKind). Tren TRANG BI day la dong hieu ung
                      # dac biet, vd 42 = 有機率出現兩倍殺傷力 (co xac suat gay sat thuong gap doi
                      # = "ti le bao kich" user hoi 26/08). Dong nay KHONG nam o bang dong phu -
                      # da kiem chung bang du lieu THAT: EquipmentAffix / EquipmentReinforced /
                      # EquipmentReinforcedValue deu khong co ma bao kich nao.
                      ("sa", "specialAbility"),
                      # q = quality (0 trang 1 luc 2 lam 3 tim 4 do). Luat CUONG HOA tra
                      # theo (fitType, a1k, quality) - thieu q la khong tinh duoc.
                      ("q", "quality")):
        v = src.get(field) or 0
        if v:
            rec[key] = int(v)
        else:
            rec.pop(key, None)


def main():
    path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    if not path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = read_items(path)

    # GIU nguyen cac truong dang co trong file cu (name/hp/sp/battle) - chi THEM restrict.
    try:
        with open(OUT, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:
        old = {}

    # CHI THEM `restrict` vao cac item DA CO trong file. KHONG ghi de "name" va KHONG them item
    # moi: ten trong file cu bi LECH BAN GHI o ~1237 muc (vd 0x1f41 = "Trang Bi Cap 40<rac>" trong
    # khi .dat la "Tui Tinh Nhan Do") - sua ten la doi hanh vi cua nhieu cho khac (log tui, thong
    # bao, doi chieu theo ten) nen phai tach thanh viec RIENG, khong tron vao fix hop do.
    by_id = {d["id"]: d for d in items}
    out = dict(old)
    n_new = 0
    for key, rec in out.items():
        try:
            tid = int(key, 16) if key.lower().startswith("0x") else int(key)
        except ValueError:
            continue
        src = by_id.get(tid) or {}
        r = src.get("restrict", 0)
        rec = dict(rec)
        if r:
            rec["restrict"] = r
            n_new += 1
        else:
            rec.pop("restrict", None)
        _set_tab_fields(rec, src)
        out[key] = rec

    # THEM item MOI (id chua co trong file). KHONG dung vao muc da co -> ten cu giu nguyen,
    # khong doi hanh vi cho nao dang doi chieu theo ten. Khong co buoc nay thi MOI item game
    # them sau nay deu hien la "item 30558" (vd event Mung Quoc Khanh).
    n_add = 0
    for tid, d in sorted(by_id.items()):
        if ("0x%04x" % tid) in out or str(tid) in out:
            continue
        name = (d.get("name") or "").strip()
        if not name:
            continue
        rec = {"name": name}
        if d.get("restrict"):
            rec["restrict"] = d["restrict"]
        _set_tab_fields(rec, d)
        out["0x%04x" % tid] = rec
        n_add += 1

    # Mo ta lay THANG tu .dat theo id cua chinh ban ghi do, khong dinh gi den ten cu trong
    # items_gamedata.json (~1237 muc dang lech ten). Bo mo ta rong cho file gon.
    desc = {}
    for tid, d in sorted(by_id.items()):
        s = (d.get("desc") or "").strip()
        if s:
            desc["0x%04x" % tid] = s
    with open(OUT_DESC, "w", encoding="utf-8") as fh:
        json.dump(desc, fh, ensure_ascii=False)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    n_nocombine = sum(1 for v in out.values() if (v.get("restrict", 0) & 4))
    print("=> %s: %d item (+%d MOI, %d co restrict != 0, %d KHONG dung de hop duoc - bit 4)"
          % (os.path.basename(OUT), len(out), n_add, n_new, n_nocombine))
    print("=> %s: %d mo ta (%.2f MB)"
          % (os.path.basename(OUT_DESC), len(desc), os.path.getsize(OUT_DESC) / 1048576.0))


if __name__ == "__main__":
    main()
