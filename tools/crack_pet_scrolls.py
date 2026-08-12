"""Sinh pet_scrolls.json: TAT CA cuon goi vo tuong (Bi Cap) co trong game.

Dung cho tinh nang "Tu phan giai cuon vo tuong rac" (Cai dat nang cao -> Tu don tui do):
moi cuon co 2 trang thai GIU LAI / PHAN GIAI, mac dinh cuon cua vo tuong CO VU KHI CHUYEN
DUNG (vkcd) = GIU LAI, con lai = PHAN GIAI.

  kind 38 (EItemKind, Bi Cap = cuon goi pet) : spare3 = npc id cua vo tuong duoc goi
  (xem tools/crack_exclusive_weapons.py - cung layout ItemData.New() 54 truong)

KHONG khoa cung: pet co vkcd nhieu con van lom, mac dinh "giu lai" chi la GOI Y - user
van doi sang "phan giai" duoc trong GUI/APK.

Nguon: gamedata_Item.dat + gamedata_Npc.dat (KHONG theo repo - copy tu client) +
exclusive_weapons.json (tools/crack_exclusive_weapons.py).

Chay: python tools/crack_pet_scrolls.py
Ghi:  pet_scrolls.json  { "<tid_hex>": {"name": ten cuon, "npc_id": id, "npc": ten tuong,
                                        "vkcd": true/false} }
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from crack_exclusive_weapons import _find                         # noqa: E402
from crack_furnace_notify import (build_reincarnation_up, read_items,  # noqa: E402
                                  to_base)
from crack_npc_table import read_npcs                             # noqa: E402

OUT = os.path.join(ROOT, "pet_scrolls.json")
VKCD = os.path.join(ROOT, "exclusive_weapons.json")
KIND_SUMMON = 38        # Bi Cap - cuon goi pet
# Cuon goi vo tuong: ten LUON "Bi Cap <ten tuong>" (vai muc viet tat "BC <ten tuong>")
NAME_RE = re.compile(r"^(BC |Bí\s*Cấp)")
# BAN DAC BIET cua mot tuong ("Than Lu Bo", "Loi Am Khong Minh", "Ma Tong Dung"...): la pet manh
# nhat game nhung KHONG co vu khi chuyen dung rieng, va ten cung KHONG trung tuong goc
# ("Than Lu Bo" != "Lu Bo") -> khong moc vao rule vkcd bang duong nao. Nhan theo TU khoa trong ten.
# So khop theo TU (tach theo dau cach) chu KHONG phai chuoi con, de "Ma" khong an vao "Mai"/"Manh".
SPECIAL_WORDS = {"Thần", "Ma", "Cuồng", "Quang", "Ám"}
# GIU LAI thu cong theo npc_id: pet xin KHONG co vkcd va KHONG dinh dang dac biet nao o tren.
# Giu qua REGEN. Them npc_id vao day khi user bao "giu con X".
KEEP_OVERRIDE_NPC = {
    22093,   # Ba Dau Vo Si
    22030,   # Ac Ma Ba Dau Yeu
    22095,   # Ngoc Tho Bao Bao
    14111,   # Tuong Nghia Cu
    12218,   # Khuong Duy
    46411,   # Thai Pho Duong Ho      lv128
    46407,   # Yen Nhan Truong Phi    lv128
    46410,   # Cam Ma Sieu            lv128
    41553,   # Dai Kieu Do Boi        lv140
    45407,   # Khuat Nguyen           lv55
}
RARE_NAME = {1: "đồng", 2: "đồng", 3: "đồng", 4: "bạc", 5: "vàng"}
SPECIAL_MIN_LV = 128    # duoi nguong nay tu khoa chi bat nham tuong thuong / quai event


def main():
    item_path = _find("gamedata_Item.dat", os.path.join("gamedata", "Data", "Item_C.dat"))
    npc_path = _find("gamedata_Npc.dat", os.path.join("gamedata", "Data", "Npc_C.dat"))
    if not item_path:
        raise SystemExit("Khong thay gamedata_Item.dat (hoac gamedata/Data/Item_C.dat)")
    items = read_items(item_path)
    # read_npcs (crack_npc_table) doc TUAN TU dung layout NpcData.New -> du 8360 npc kem
    # level/rare. parse_npc_names cu quet byte theo mau nen bo sot dung nhung ban dac biet
    # (46407 "Yen Nhan Truong Phi", 45437 "Ma Quan Vu"...) - tung phai lay "khong tra duoc ten"
    # lam dau hieu ban dac biet, nay khong can meo do nua.
    npcs = read_npcs(npc_path) if npc_path else {}

    vk = json.load(open(VKCD, encoding="utf-8"))
    vk_npc = {int(v["npc_id"]) for v in vk.values() if v.get("npc_id")}
    # Cuon cua BAN NANG CAP / CHUYEN SINH cua mot tuong van la tuong do, vd:
    #   "BC Truong Giac Chan" -> npc 41003 --(lan nguoc)--> 10001 Truong Giac (CO vkcd)
    # exclusive_weapons.json chi liet ke npc GOC nen phai LAN NGUOC chuoi truoc khi doi chieu,
    # khong thi ban nang cap cua tuong xin bi xep "phan giai".
    # (Chuoi nay gom tu canh K.Toa/T.Tinh - no noi ca ban nang cap lan ban chuyen sinh.)
    up = build_reincarnation_up(items)
    vk_names = {v["name"].strip() for i, v in npcs.items() if i in vk_npc and v.get("name")}

    out = {}
    for d in items:
        if d["kind"] != KIND_SUMMON:
            continue
        npc = d["spare3"]
        # kind 38 = "dung vao thi nhan duoc mot thu gi do", KHONG rieng cuon goi vo tuong:
        #   spare3 = 0  -> hop qua / phieu chon ("Qua Tan Thu", "Phieu chon vu khi chuyen dung")
        #   spare3 > 0  -> VAN con thu cuoi ("Ba Dau", "Bach Ho Phieu"), chan dung, thoi trang,
        #                  do an... vi chung cung tro vao mot npc id.
        # Loc kind 38 + spare3>0 ra 807 muc thi 330 muc KHONG phai cuon -> bot se phan giai
        # nham thu cuoi/chan dung. Cuon goi vo tuong LUON ten "Bi Cap <ten tuong>" (3 muc viet
        # tat "BC <ten tuong>"); da doi chieu: khong co cuon nao mang chu "Cap" ma nam ngoai.
        if not npc or not NAME_RE.match(d["name"] or ""):
            continue
        info = npcs.get(npc) or {}
        npc_name = info.get("name", "")
        # Ban DAC BIET cua pet xin -> mac dinh GIU LAI (user van doi 2 chieu trong GUI). Cac dang:
        #  1) Tu khoa Than/Ma/Cuong/Quang/Am VA lv >= 128. PHAI co dieu kien level: tu khoa khong
        #     thi an nham tuong thuong / quai event trung am tiet ("Bi Ngo Ma" lv40 = quai
        #     Halloween, "Chu Quang" lv99, "Sa Ma Kha" lv126). Tu lv128 tro len toan ban dac biet
        #     that, duoi do khong con cai nao -> nguong cat sach.
        #  2) Series Lv80 ("... 80", npc 38520-38527) = ban Lv80 cua pet base xin.
        #  3) Skin theo mua (Noel...) = ban suu tap cua pet base xin.
        _w = set((d["name"] or "").replace(".", " ").split()) | set(npc_name.replace(".", " ").split())
        special = ((_w & SPECIAL_WORDS) and info.get("level", 0) >= SPECIAL_MIN_LV) \
            or (d["name"] or "").rstrip().endswith(" 80") or "Noel" in npc_name
        # Ban nang cap thuong DOI npc_id nhung GIU NGUYEN ten tuong (npc 46408 = "Luu Bi"), nen
        # doi chieu vkcd theo CA npc id lan TEN tuong.
        vkcd = (to_base(npc, up) in vk_npc or npc_name.strip() in vk_names
                or bool(special) or npc in KEEP_OVERRIDE_NPC)
        out["0x%04x" % d["id"]] = {
            "name": d["name"],
            "npc_id": npc,
            "npc": npc_name,
            "lv": info.get("level", 0),
            "rare": RARE_NAME.get(info.get("rare", 0), ""),
            "vkcd": vkcd,
        }
    out = dict(sorted(out.items(), key=lambda kv: kv[1]["name"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    n_keep = sum(1 for v in out.values() if v["vkcd"])
    print("=> %s: %d cuon (%d co vkcd -> mac dinh GIU LAI, %d -> PHAN GIAI)"
          % (os.path.basename(OUT), len(out), n_keep, len(out) - n_keep))


if __name__ == "__main__":
    main()
