"""Sinh quests.json (data cho mode "Lam quest") tu marks.json.

marks.json do tools/crack_mark_steps.py sinh tu .dat cua client (khong theo repo). quests.json chi
giu cac chuoi quest bot lam, gon de dong goi vao exe/APK.

Moi quest trong chuoi:
  id    = ma nhiem vu CHAN (chua cac buoc, la mission trong goi 0x18 sub06 khi dang lam)
  bit   = bitId cua ma LE ngay sau (co DA XONG, doc bang client.mark_flag_get)
  nhan  = noi nhan quest - user doc trong game (data client khong co)

Danh sach 8 quest Bat dai Cu Thu do user chot theo ten trong game 03/10/2026 (KNOWLEDGE.md muc
"NHIEM VU (Mark)").

Chay: python tools/build_quests.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "marks.json")
OUT = os.path.join(ROOT, "quests.json")

# KICH BAN tung quest - CHI lay tu capture (khong doan: chon sai ma = server ngat ket noi).
#   nhan : diem NHAN quest (data client khong co): map, toa do dung, "npc" HOAC "cua", ma chon
#   buoc : {so buoc: {"chon": [ma...], "truoc": [cua su kien phai cham truoc],
#                     "cua": idx}}  <- buoc data ghi ev_kind 0 (chi co toa do) THAT RA la cham
#                                     cua su kien AN tai toa do do (capture 10324)
# Quest CHUA co kich ban -> bot khong lam (log + dung yen).
KICH_BAN = {
    # captures/cs1_10806_khungthuong_20261003.pcap - nhan khong chon; B1 NPC 1 (= data) chon muc 1;
    # B2 NPC 1 o Dong Bach Lang danh boss; B3 NPC 1 (= data).
    10806: {"nhan": {"scene": 19176, "x": 490, "y": 330, "npc": 1, "chon": []},
            "buoc": {"1": {"chon": [30]}}},
    # captures/cs1_10564_letethannuoc_20261003.pcap - nhan chon muc 1; B1 NPC 1 (= data) danh boss,
    # server nhay +2 buoc (2 -> 4, B2/B3 tu xong); B4 NPC 1 (= data).
    10564: {"nhan": {"scene": 56101, "x": 330, "y": 350, "npc": 1, "chon": [30]},
            "buoc": {}},
    # captures/cs1_10360_hoadiem_20261003.pcap - nhan chon muc 1; B1/B2/B3 la cua 6/2/3 dung data;
    # B3 user chon MUC 2 (31) -> server nhay +3 buoc (3 -> 6), bo qua B4/B5 (nhanh "lam bo ha").
    # Cong 11 o Thanh Chau ra 55000 HOAC 58000 ngau nhien - execute_smart_route da tu plan lai.
    10360: {"nhan": {"scene": 55003, "x": 390, "y": 350, "npc": 2, "chon": [30]},
            "buoc": {"3": {"chon": [31]}}},
    # captures/cs1_10328_thutochaythoat_20261003.pcap - NHAN bang CUA AN 4 (khong phai NPC) co chon
    # muc 1; B1 cua an 2 (server lam luon B2); B3 cua an 5 (server lam luon B4 + bat co xong).
    # B2/B4 rieng chua capture (chi xay ra khi rot giua su kien) -> khong doan.
    10328: {"nhan": {"scene": 56501, "x": 1170, "y": 1330, "cua": 4, "chon": [30]},
            "buoc": {"1": {"cua": 2}, "3": {"cua": 5}}},
    # captures/cs1_10326_phannobien_20261003.pcap - nhan co chon muc 1; B1 = cua an 2 o Bot Hai,
    # danh boss, server lam LUON B2 + B3 trong cung su kien roi bat co xong
    10326: {"nhan": {"scene": 11021, "x": 970, "y": 350, "npc": 4, "chon": [30]},
            "buoc": {"1": {"cua": 2}}},
    # captures/cs1_10324_thiendoc_20261003.pcap - B2..B4 la cua an; B4 lam luon ca B5 (server xoa
    # mission + bat co trong cung su kien)
    10324: {"nhan": {"scene": 13243, "x": 190, "y": 470, "npc": 1, "chon": []},
            "buoc": {"2": {"cua": 5}, "3": {"cua": 2, "chon": [30]}, "4": {"cua": 3}}},
    # captures/cs1_10384_tuyetdong_20261003.pcap - khong co lan chon nao
    10384: {"nhan": {"scene": 19011, "x": 610, "y": 810, "npc": 1, "chon": []},
            "buoc": {}},
    # captures/cs1_10528_thaiho_20261003.pcap - B1/B2 chon muc 1 (30); B2 cham cua 3 truoc NPC
    10528: {"nhan": {"scene": 18001, "x": 1310, "y": 250, "npc": 4, "chon": []},
            "buoc": {"1": {"chon": [30]},
                     "2": {"chon": [30], "truoc": [{"cua": 3, "x": 3651, "y": 365}]}}},
}

CHUOI = {
    "cs1_cu_thu": {
        "label": "Chuyển sinh 1 - Bát đại Cự Thú",
        "quests": [
            (10324, "Uyển Thành - Dự Châu"),
            (10326, "Làng Phùng Lai - Thanh Châu"),
            (10328, "Động Bạch Sơn - Cao Câu Ly"),
            (10360, "Nhà Bắc Tinh Quân"),
            (10384, "Thôn Vọng Bình - Liêu Đông"),
            (10528, "Đại lộ Kiến Nghiệp - Giang Đông"),
            (10564, "Quế Lâu Bộ - Cao Câu Ly"),
            (10806, "Trướng Ô Hoàn - Liêu Đông"),
        ],
    },
}


def main():
    with open(SRC, encoding="utf-8") as f:
        marks = json.load(f)
    out = {}
    for key, ch in CHUOI.items():
        qs = []
        for mid, nhan in ch["quests"]:
            m = marks[str(mid)]
            done = marks[str(mid + 1)]
            assert done["bitId"], f"{mid + 1} khong co bitId"
            steps = {}
            for s, st in m["steps"].items():
                steps[s] = {
                    "desc": st["desc"].strip(),
                    "conds": [{k: c[k] for k in ("kind", "id", "count", "scene", "x", "y")}
                              for c in st["conds"]],
                    "scene": st["endScene"], "x": st["endX"], "y": st["endY"],
                    "ev_kind": st["endEvKind"], "ev_id": st["endEvId"],
                    "team": st["checkTeam"],
                }
            kb = KICH_BAN.get(mid)
            if kb:
                for so, them in kb.get("buoc", {}).items():
                    assert so in steps, f"{mid} khong co buoc {so}"
                    steps[so].update(them)
            qs.append({"id": mid, "bit": done["bitId"], "name": m["name"], "nhan": nhan,
                       "kich_ban": bool(kb), "nhan_tai": (kb or {}).get("nhan"),
                       "steps": steps})
        out[key] = {"label": ch["label"], "quests": qs}
    # Chuoi sinh tu Eve.emg (documents/QUEST_CHINH_TUYEN.md): data o main_quests.json
    # (tools/crack_eve_quest.py); o day chi giu label de GUI/APK doc CHUNG mot danh sach chuoi.
    # Phu tuyen chua lam -> chua hien (user 08/10).
    out["chinh_tuyen"] = {"label": "Chính tuyến", "nguon": "main_quests.json"}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{OUT}: " + ", ".join(f"{k}={len(v.get('quests') or ())} quest" for k, v in out.items()))


if __name__ == "__main__":
    main()
