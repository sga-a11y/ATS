"""Sinh main_quests.json (quest chinh tuyen + phu tuyen) tu kich ban SERVER nam trong Eve.emg.

Vi sao: phan NpcEvent + Fight cua moi scene trong `CompreseData/Eve.emg` la NGUYEN dieu kien + ket
qua cua tung NPC/cua (client doc vao nhung khong dung). Doi chieu 8/8 capture Cu Thu: khop cho nhan,
cua an, ma chon, nhay buoc, boss -> khong can capture tung quest nhu CS1 (documents/QUEST_CHINH_TUYEN.md).

Cau truc (crack `_lua_dec/Data/Eve/*.lua`, thu tu doc CO DINH):
    Npc -> Goods -> Door -> Mine -> Surface -> SceneInfo -> Group -> NpcEvent -> Fight
NpcEvent: [EveNo u16][ten 9B][when 4 x bool][n u8] n x Condition
  Condition: [no u8][cls u8][par u16][pst u8][ops u8][val i32][ctime f64][toRes u8][and u8][sub u16]
             [n u8] n x Result [grp u16][no u8][type u8][cls u8][par u16][pst u8][val i32][mean u16]
  `and` = so dieu kien LIEN NHAU (ke ca chinh no) AND voi nhau, ket qua nam o dieu kien dau nhom.
Ma da giai (KNOWLEDGE.md muc "KICH BAN SERVER TRONG Eve.emg"):
  DK cls2 pst1 = buoc mission · cls2 pst2 ops0 = chua nhan · cls2 pst3 = co xong (bitId cua ma)
  DK cls10 par=surface pst=ma chon · cls8 pst1/2/3 = thang/thua/chay tran · cls7 pst1 = cap (nghi)
  KQ t0 c2 pst1 val N = mission +N buoc · t3 mean = vao tran Fight[mean] · t6 = cho CHON
  ops 1 < · 2 > · 3 <= · 4 >= · 5 == · 6 !=

Can: gamedata/Eve.emg (khong theo git, keo tu MuMu - xem KNOWLEDGE.md), marks.json
(tools/crack_mark_steps.py), npc_table.json.
Chay: python tools/crack_eve_quest.py
"""
from __future__ import annotations

import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from crack_eve_surface import read_index  # noqa: E402

EVE = os.path.join(ROOT, "gamedata", "Eve.emg")
MARKS = os.path.join(ROOT, "marks.json")
NPCS = os.path.join(ROOT, "npc_table.json")
OUT = os.path.join(ROOT, "main_quests.json")

# Mark kind (MarkData.lua) va NHAN trong game (string.GetMissionKind -> TextData 20149/50/51):
# 1 主線 [Chinh] · 2 支線 [Huong Dan] (12292 Huong Dung, 12296 Giup Luu Yen dua thu...) · 3 指引 [Phu].
# User 08/10: "giup luu yen la quest khac" -> chuoi chinh tuyen CHI loai 1, loai 2 tach rieng.
KINDS = {1: "chinh_tuyen", 2: "huong_dan", 3: "phu_tuyen"}
OPS = {1: lambda a, b: a < b, 2: lambda a, b: a > b, 3: lambda a, b: a <= b,
       4: lambda a, b: a >= b, 5: lambda a, b: a == b, 6: lambda a, b: a != b}


class R:
    def __init__(self, b: bytes, i: int):
        self.b, self.i = b, i

    def f(self, fmt: str):
        v = struct.unpack_from("<" + fmt, self.b, self.i)
        self.i += struct.calcsize("<" + fmt)
        return v if len(v) > 1 else v[0]

    def bytes(self, n: int) -> list:
        v = list(self.b[self.i:self.i + n])
        self.i += n
        return v


def parse_scene(data: bytes, off: int) -> dict:
    """Mot scene cua Eve.emg. Luu y: KHONG viet `r.i += r.f(..)` - ve trai doc r.i TRUOC khi f() tang."""
    r = R(data, off)
    npcs = {}
    for _ in range(r.f("i")):
        nid, npcid, ec = r.f("HHH")
        evs = r.bytes(ec)
        n = r.f("B")
        r.i += n                                   # saleKinds
        n = r.f("B")
        r.i += (n + 1) * 8                         # motionNodes [0..n]
        r.i += 7 + 16 + 8                          # motion*, roleGrid, moveOffsetGrid
        px, py = r.f("ii")
        r.i += 6 + 32 + 4                          # roleStatus, inner/outerNode, trace*, close
        npcs[nid] = {"npcId": npcid, "events": evs, "x": px, "y": py}
    n = r.f("H")
    r.i += n * 13                                  # Goods
    doors = {}
    for _ in range(r.f("H")):
        did, ec = r.f("HH")
        evs = r.bytes(ec)
        gx, gy, gw, gh = r.f("iiii")
        r.i += 6
        doors[did] = {"events": evs, "x": (max(gx, 0) - 1) * 20 + gw * 10,
                      "y": (max(gy, 0) - 1) * 20 + gh * 10}
    mines = {}
    for _ in range(r.f("H")):                     # Mine (vung "dia loi" SERVER tu kich hoat khi di vao)
        mid, ec = r.f("HH")
        evs = r.bytes(ec)
        gx, gy, gw, gh = r.f("iiii")
        r.i += 1                                   # sizeKind
        mines[mid] = {"events": evs, "x0": (gx - 1) * 20, "y0": (gy - 1) * 20,
                      "x1": (gx - 1 + gw) * 20, "y1": (gy - 1 + gh) * 20, "o": gw * gh}
    for _ in range(r.f("H")):                     # Surface
        _sid, _rel, sc = r.f("HHB")
        r.i += 3 + sc * 5
    for _ in range(r.f("H")):                     # SceneInfo
        r.i += 2 + 2 + 2 + 8 + 1 + 21 + 2 + 1
    for _ in range(r.f("H")):                     # Group
        r.i += 2 + 2 + 1 + 1
        n = r.f("B")
        r.i += n * 2 + 1
    events, when = {}, {}
    for _ in range(r.f("H")):
        eno = r.f("H")
        r.i += 9
        when[eno] = tuple(r.bytes(4))              # when (click/stroke/area/serStroke)
        conds = []
        for _ in range(r.f("B")):
            _no, cls, par, pst, ops, val, _t, _tores, andn, _sub, rn = r.f("BBHBBidBBHB")
            res = []
            for _ in range(rn):
                _g, _rno, rt, rc, rp, rps, rv, rm = r.f("HBBBHBiH")
                res.append((rt, rc, rp, rps, rv, rm))
            conds.append({"cls": cls, "par": par, "pst": pst, "ops": ops, "val": val,
                          "and": andn, "res": res})
        events[eno] = conds
    fights = {}
    for _ in range(r.f("H")):
        eno = r.f("H")
        r.i += 3
        enemies = []
        for _side in range(2):
            for _ in range(r.f("H")):
                _no, npcid, _pos, _ai = r.f("HHBB")
                enemies.append(npcid)
        for _ in range(r.f("H")):
            r.i += 2 + 9
            n = r.f("B")
            r.i += n * 13
        r.i += 4
        fights[eno] = enemies
    return {"npcs": npcs, "doors": doors, "mines": mines, "events": events, "fights": fights,
            "when": when}


def nhom(conds: list) -> list:
    """Gom dieu kien thanh nhom AND: [(chi so, [dieu kien...], ket qua)]."""
    out, i = [], 0
    while i < len(conds):
        n = max(1, conds[i]["and"])
        out.append((i, conds[i:i + n], conds[i]["res"]))
        i += n
    return out


def chu_su_kien(sc: dict, eno: int):
    """(kieu, idx, x, y) cua NPC/cua mang su kien eno; None neu khong ai mang."""
    for k in sorted(sc["npcs"]):
        n = sc["npcs"][k]
        if eno in n["events"]:
            return ("npc", k, n["x"], n["y"])
    for k in sorted(sc["doors"]):
        d = sc["doors"][k]
        if eno in d["events"]:
            return ("cua", k, d["x"], d["y"])
    return None


XONG = 99   # "tang" dac biet: buoc tra quest (bat co xong ma le mid+1, xoa mission)
CHUYEN = 98  # "tang" dac biet: xoa mission + giao quest khac (chuyen tiep cot truyen)


def tang(res, mid: int) -> int:
    """So buoc mission mid duoc cong trong danh sach ket qua (0 = khong, XONG = tra quest).

    Buoc cuoi KHONG cong buoc: capture 10384 B3 = `0x18 0400` xoa mission + `0x18 05` bat co
    -> data KQ `t0 c2 par mid pst3 val0` + `t0 c2 par mid+1 pst1 val1`.
    """
    if any(t == 0 and c == 2 and p == mid + 1 and ps == 1 and v > 0 for (t, c, p, ps, v, _m) in res):
        return XONG
    k = sum(v for (t, c, p, ps, v, _m) in res if t == 0 and c == 2 and p == mid and ps == 1 and v > 0)
    if k:
        return k
    # XOA mission KEM giao quest/bat co khac = CHUYEN TIEP (Gian Ung 12136: tra loi dung 3 cau ->
    # xoa 12288 + giao 10001). Xoa TRON = BO QUEST (10528 chon 31 o 18506) -> khong tinh. [nghi]
    if any(t == 0 and c == 2 and p == mid and ps == 3 and v == 0 for (t, c, p, ps, v, _m) in res) \
            and any(t == 0 and c == 2 and p != mid and ps == 1 and v > 0
                    for (t, c, p, ps, v, _m) in res):
        return CHUYEN
    return 0


def gia_nhap(res) -> int:
    """So NPC XIN GIA NHAP (KQ class 3 style 1 - EventHandler.lua "要求加入玩家"): client chi nhan
    khi dang co < Role.maxFollowNpc (= 4) vo tuong. 10001 B3: Truong Phi theo (user 08/10: "can slot
    trong cua pet")."""
    return sum(1 for (t, c, _p, ps, _v, _m) in res if t == 0 and c == 3 and ps == 1)


def di_tiep(groups, res, mid, sau, sc, depth=0):
    """Tu ket qua `res` cua nhom kich hoat, di theo CHON / THANG TRAN toi khi mission mid len buoc.

    Tra list nhanh [(so buoc tang, [ma chon...], [quai tung tran...], so NPC gia nhap)], rong =
    nhanh khong len buoc.
    `sau` = chi so dieu kien cua nhom kich hoat; nhom chon/tran tra loi nam SAU no trong su kien.
    """
    if depth > 4:
        return []
    gn = gia_nhap(res)
    k = tang(res, mid)
    if k:
        return [(k, [], [], gn)]
    out = []
    for (t, c, p, ps, v, m) in res:
        if t == 6:                                 # cho chon tren surface m
            for i, g, r2 in groups:
                if i <= sau or len(g) < 1:
                    continue
                c0 = g[0]
                if c0["cls"] == 10 and c0["par"] == m:
                    for (kk, chon, tran, g2) in di_tiep(groups, r2, mid, i, sc, depth + 1):
                        out.append((kk, [c0["pst"]] + chon, tran, gn + g2))
        elif t == 3:                               # vao tran Fight[m] -> nhom THANG (cls8 pst1)
            boss = sc["fights"].get(m, [])
            for i, g, r2 in groups:
                if i <= sau:
                    continue
                c0 = g[0]
                if c0["cls"] == 8 and c0["pst"] == 1:
                    for (kk, chon, tran, g2) in di_tiep(groups, r2, mid, i, sc, depth + 1):
                        out.append((kk, chon, [boss] + tran, gn + g2))
                    break                          # nhom thang dau tien sau tran
    return out


def dk_ra(g: list) -> list:
    """Dieu kien cua nhom kich hoat, dang gon [cls, par, pst, ops, val] cho bot tu danh gia."""
    return [[c["cls"], c["par"], c["pst"], c["ops"], c["val"]] for c in g]


def chon_nhanh(nhanh: list):
    """Nhieu nhanh cung len buoc -> uu tien KHONG danh tran, roi ma chon nho nhat."""
    return sorted(nhanh, key=lambda x: (len(x[2]) > 0, x[1]))[0]


def co_tran(groups, res, sau, depth=0) -> bool:
    """Nhanh ket qua `res` co dan vao tran khong (di theo ca chon long nhau)."""
    if depth > 4:
        return False
    for (t, _c, _p, _ps, _v, m) in res:
        if t == 3:
            return True
        if t == 6:
            for i, g, r2 in groups:
                if i > sau and g[0]["cls"] == 10 and g[0]["par"] == m and co_tran(groups, r2, i, depth + 1):
                    return True
    return False


def bang_chon(sc: dict, kieu: str, idx: int, mid: int) -> dict:
    """{surface: ma} cho MOI cau hoi chon ma NPC/cua nay co the bat ra.

    Mot NPC mang nhieu su kien va server chay CA (capture 10806 B1: NPC 1 o 19175 mang su kien 2
    cua quest 10600 + su kien 4 cua 10806; chon 30 la tra loi su kien 2 -> "kem mission phu 10600
    +1"). Surface cua quest mid: ma lam mid len buoc (uu tien khong danh). Surface khac: ma NHO
    NHAT khong dan vao tran.
    """
    chu = sc["npcs"].get(idx) if kieu == "npc" else sc["doors"].get(idx)
    if not chu:
        return {}
    out = {}
    for eno in chu["events"]:
        groups = nhom(sc["events"].get(eno, []))
        for i, g, res in groups:
            for (t, _c, _p, _ps, _v, s) in res:
                if t != 6 or s in out:
                    continue
                cac = [(j, g2[0]["pst"], r2) for j, g2, r2 in groups
                       if j > i and g2[0]["cls"] == 10 and g2[0]["par"] == s]
                if not cac:
                    continue
                len_buoc = [(co_tran(groups, r2, j), ma) for j, ma, r2 in cac
                            if di_tiep(groups, r2, mid, j, sc)]
                if len_buoc:
                    out[s] = sorted(len_buoc)[0][1]
                else:
                    yen = sorted(ma for j, ma, r2 in cac if not co_tran(groups, r2, j))
                    out[s] = yen[0] if yen else sorted(ma for _j, ma, _r in cac)[0]
    return {str(k): v for k, v in sorted(out.items())}


def cho_theo(sc: dict, res, npc_id: int) -> bool:
    """Ket qua co cho NPC npc_id DI THEO khong: `t0 c3 par K pst1` (NPC K cua scene xin gia nhap)
    hoac `t0 c8 par npcId pst1` (server them thang; `pst2` = xoa - 10023 B1 tra ngua 18005)."""
    for (t, c, p, ps, _v, _m) in res:
        if t != 0 or ps != 1:
            continue
        if c == 3 and (sc["npcs"].get(p) or {}).get("npcId") == npc_id:
            return True
        if c == 8 and p == npc_id:
            return True
    return False


def nhanh_theo(groups, res, npc_id, mid, sau, sc, depth=0):
    """Nhanh tu `res` toi khi NPC npc_id di theo ma mission mid KHONG len buoc (len buoc = chinh
    su kien buoc, khong phai cho lay NPC). Tra [([(surface, ma)...], [quai tung tran...])]."""
    if depth > 4 or tang(res, mid):
        return []
    if cho_theo(sc, res, npc_id):
        return [([], [])]
    out = []
    for (t, c, p, ps, v, m) in res:
        if t == 6:
            for i, g, r2 in groups:
                if i > sau and g[0]["cls"] == 10 and g[0]["par"] == m:
                    for chon, tran in nhanh_theo(groups, r2, npc_id, mid, i, sc, depth + 1):
                        out.append(([(m, g[0]["pst"])] + chon, tran))
        elif t == 3:
            boss = sc["fights"].get(m, [])
            for i, g, r2 in groups:
                if i > sau and g[0]["cls"] == 8 and g[0]["pst"] == 1:
                    for chon, tran in nhanh_theo(groups, r2, npc_id, mid, i, sc, depth + 1):
                        out.append((chon, [boss] + tran))
                    break
    return out


def lay_npc(scenes: dict, npc_lv: dict, mid: int, n: int, npc_id: int, scene_goi_y: int) -> list:
    """Cho DUA NPC npc_id ma buoc n cua mid can dan theo (`can` kind 1), khi KHONG phai buoc truoc
    tu dua. 10023 B1 (log p52 09/10): Ma Phu 12001 NPC 6 doi `cls9 = 18005` (ngua di theo); ngua =
    NPC 9 cung scene, noi chuyen -> surface 11 -> chon 30 -> `t0 c3 par9 pst1` xin gia nhap.
    Uu tien scene goi y (st.conds scene), khong danh tran."""
    out = []
    for sid in sorted(scenes, key=lambda s: (s != scene_goi_y, s)):
        sc = scenes[sid]
        for eno, conds in sc["events"].items():
            groups = nhom(conds)
            if not any(cho_theo(sc, r, npc_id) for _i, _g, r in groups):
                continue
            chu = chu_su_kien(sc, eno)
            if chu is None:
                continue
            for i, g, res in groups:
                if g[0]["cls"] in (8, 10):
                    continue
                if not any(c["cls"] == 2 and c["par"] == mid and c["pst"] == 1 and c["ops"] in OPS
                           and OPS[c["ops"]](n, c["val"]) for c in g):
                    continue
                for chon, tran in nhanh_theo(groups, res, npc_id, mid, i, sc):
                    cm = bang_chon(sc, chu[0], chu[1], mid)
                    cm.update({str(s): ma for s, ma in chon})
                    out.append({"npc": npc_id, "scene": sid, "kieu": chu[0], "idx": chu[1],
                                "x": chu[2], "y": chu[3], "chon": [ma for _s, ma in chon],
                                "chon_map": cm, "tran": bool(tran), "boss": cap_boss(npc_lv, tran),
                                "dk": dk_ra(g)})
        if out:
            break
    return sorted(out, key=lambda u: (u["tran"], u["chon"]))[:1]


def chon_mo(sc: dict, npc_lv: dict, x: int, y: int):
    """Vung MO de dung danh quai lay item khi diem client chi KHONG co NPC/cua (`evKind 0`).

    Map mo (vd 12591 mo Trac Quan) KHONG co tran gap ngau nhien: tran chi ra khi di TRONG vung mo
    (EventManager.lua `Mine = 7 --地雷(現在由Server觸發)`). Diem client chi (1250,1030) nam GIUA mo 2
    va mo 3 -> dung do 0 tran (log p52 09/10 19:14-00:11). User 10/10: "chon mo theo quest" -> mo
    GAN diem quest chi nhat; bang nhau thi quai lv thap. Bo vung 1 o (mo 1 = (1,1,1,1) goc map)."""
    ds = []
    for k, m in sorted((sc.get("mines") or {}).items()):
        quai = [n for eno in m["events"] for _i, _g, res in nhom(sc["events"].get(eno, []))
                for (t, _c, _p, _ps, _v, mm) in res if t == 3 for n in sc["fights"].get(mm, [])]
        if not quai or m["o"] <= 1:
            continue
        dx = max(m["x0"] - x, 0, x - m["x1"])
        dy = max(m["y0"] - y, 0, y - m["y1"])
        lv = max(npc_lv.get(n, 0) for n in quai)
        ds.append(((dx * dx + dy * dy) ** 0.5, lv, k, m, sorted(set(quai))))
    if not ds:
        return None
    _d, lv, k, m, quai = sorted(ds, key=lambda t: (t[0], t[1], t[2]))[0]
    return {"id": k, "x0": m["x0"], "y0": m["y0"], "x1": m["x1"], "y1": m["y1"], "lv": lv,
            "quai": quai}


QUAI_GAN = 400   # px: quai "cham la danh" trong ban kinh nay quanh diem farm -> dung yen cho no lao vao


def quai_lao_vao(sc: dict) -> list:
    """NPC quai HIEN TREN MAP tu cham nguoi la vao tran: su kien serStroke (`when[3]`) co KQ vao tran.
    12841 Hac Son GiapBinh (1770,840): dung yen o (1870,890) la vao tran sau 5s (log p52 10/10)."""
    return [(k, n["x"], n["y"]) for k, n in sorted(sc["npcs"].items())
            if any((sc["when"].get(e) or (0, 0, 0, 0))[3]
                   and any(t == 3 for _i, _g, res in nhom(sc["events"].get(e, []))
                           for (t, _c, _p, _ps, _v, _m) in res)
                   for e in n["events"])]


def nha_tro(scenes: dict, scene_goi_y: int):
    """Chu NHA TRO de gui vo tuong: nhom chon (`cls10 par=surface pst=ma`) co KQ `t7 c7 pst4`.
    12244 Dai Truong Quy surface 2 "Võ Tướng" (ma 32) -> `t7 c7 pst4`; "Nơi ở" (31) -> `pst5`.
    Uu tien cung scene voi buoc quest (12290 B7: Ly Chau cung map 12244)."""
    ds = []
    for sid in sorted(scenes):
        sc = scenes[sid]
        for k, n in sorted(sc["npcs"].items()):
            for e in n["events"]:
                for _i, g, res in nhom(sc["events"].get(e, [])):
                    c0 = g[0]
                    if c0["cls"] == 10 and any(t == 7 and c == 7 and ps == 4
                                               for (t, c, _p, ps, _v, _m) in res):
                        ds.append((sid != scene_goi_y, sid, k, n["x"], n["y"],
                                   {str(c0["par"]): c0["pst"]}))
    if not ds:
        return None
    _x, sid, k, x, y, chon = sorted(ds, key=lambda t: (t[0], t[1], t[2]))[0]
    return {"scene": sid, "kieu": "npc", "idx": k, "x": x, "y": y, "chon_map": chon}


def lay_item(scenes: dict, mid: int, c: dict, npc_lv=None):
    """Cho LAY ITEM cua dieu kien `kind 3` = dung cho client TU DAN DUONG khi chua du item
    (`MarkManager.Navigation`: dieu kien chua dat -> di toi condition.sceneId/position; eventKind
    1 = toi noi TU BAM NPC eventId, 2 = cua). Toa do 0 -> client cung bao khong dan duoc (21264).
    12288 B4 "Giao thit xay": 12808 NPC 13 = quai Banh Bao Thit (cham vao -> Fight 16)."""
    if not c.get("scene") or not (c.get("x") or c.get("y")):
        return None
    u = {"item": c["id"], "count": max(1, int(c["count"])), "scene": c["scene"], "x": c["x"],
         "y": c["y"], "kieu": None, "idx": 0, "chon_map": {}, "tran": False, "bam": False}
    sc = scenes.get(c["scene"])
    kieu = {1: "npc", 2: "cua"}.get(c.get("evKind"))
    chu = sc and kieu and (sc["npcs"] if kieu == "npc" else sc["doors"]).get(c.get("evId"))
    if not chu and sc:
        mo = chon_mo(sc, npc_lv or {}, int(c["x"]), int(c["y"]))
        if mo:
            u["mo"] = mo                           # di lai TRONG vung mo nay (dung yen = 0 tran)
        elif not any(((x - int(c["x"])) ** 2 + (y - int(c["y"])) ** 2) ** 0.5 <= QUAI_GAN
                     for _k, x, y in quai_lao_vao(sc)):
            # Khong co quai lao vao quanh diem -> chi co tran ngau nhien KHI DI: 11176 map 12582
            # (1300,1000) dung yen 21 phut 0 tran, di tren cung map 6s la gap (log p52 10/10).
            u["di_lai"] = True
    if chu:
        # bam = co su kien kich hoat bang CLICK (when[0]); 12808 NPC 13 chi co serStroke (quai tu
        # cham nguoi) -> KHONG bam, chi toi gan + danh tran gap phai.
        u.update(kieu=kieu, idx=c["evId"], chon_map=bang_chon(sc, kieu, c["evId"], mid),
                 bam=kieu == "cua" or any((sc["when"].get(eno) or (0,))[0] for eno in chu["events"]),
                 tran=any(t == 3 for eno in chu["events"] for _i, _g, res in nhom(sc["events"].get(eno, []))
                          for (t, _c, _p, _ps, _v, _m) in res))
    return u


def cap_boss(npc_lv: dict, tran: list) -> int:
    return max([npc_lv.get(n, 0) for t in tran for n in t] or [0])


def main():
    with open(EVE, "rb") as fh:
        data = fh.read()
    with open(MARKS, encoding="utf-8") as fh:
        marks = json.load(fh)
    with open(NPCS, encoding="utf-8") as fh:
        npc_lv = {int(k): int(v.get("level") or 0) for k, v in json.load(fh).items()}
    scenes = {sid: parse_scene(data, off) for sid, (off, _size) in read_index(data).items()}

    muc_tieu = {int(k): v for k, v in marks.items() if v["kind"] in KINDS and v["steps"]}
    lam = {mid: {} for mid in muc_tieu}            # mid -> {buoc: [ung vien]}
    nhan = {mid: [] for mid in muc_tieu}
    # THU TU COT TRUYEN: mid <- cac mission/co nam trong dieu kien cua nhom GIAO mid. Quest chinh
    # tuyen hay duoc server TU GIAO khi xong buoc quest truoc (12286 B1 -> 12288 -> Gian Ung ->
    # 10001), xep theo ma la sai (log 08/10 qg506: 10098 giua truyen len dau danh sach).
    # Do thi tren MOI ma nhiem vu (chuan hoa ve ma CHAN): nhieu quest phu thuoc co KHONG CO BUOC
    # (vd 10384 can co 10401 "Tien vao Lieu Dong") - bo qua chung thi chuoi dut, do sau ve 0.
    # Chuan hoa: ma CO BUOC = chinh no; ma ngay sau ma co buoc = co xong cua ma do. KHONG dung
    # "chan/le": 10001 Dao Vien Ket Nghia la ma LE co buoc (co xong = 10002).
    co_buoc = {int(k) for k, v in marks.items() if v.get("steps")}

    def chuan(p):
        return p - 1 if (p not in co_buoc and p - 1 in co_buoc) else p

    tat_ca = {chuan(int(k)) for k in marks}
    truoc = {mid: set() for mid in tat_ca}
    for sid in sorted(scenes):
        sc = scenes[sid]
        for eno, conds in sc["events"].items():
            chu = chu_su_kien(sc, eno)
            if chu is None:
                continue
            groups = nhom(conds)
            giao_ev = {chuan(p) for _i, _g, rs in groups for (t, c, p, ps, v, _m) in rs
                       if t == 0 and c == 2 and ps == 1 and v > 0 and chuan(p) in tat_ca}
            for i, g, res in groups:
                c0 = g[0]
                if c0["cls"] in (8, 10):           # nhom tra loi chon / ket qua tran, khong kich hoat
                    continue
                buoc_dk = {}
                for c in g:
                    if c["cls"] == 2 and c["pst"] == 1 and c["par"] in muc_tieu and c["ops"] in OPS:
                        buoc_dk[c["par"]] = c
                for mid in giao_ev - set(buoc_dk):
                    if any(c["cls"] == 2 and c["par"] == mid and c["pst"] == 1 for c in g):
                        continue                   # tang buoc mission khong co trong muc_tieu
                    if di_tiep(groups, res, mid, i, sc):
                        truoc[mid] |= {chuan(c["par"]) for c in g if c["cls"] == 2
                                       and c["par"] not in (mid, mid + 1)
                                       and not (c["pst"] == 3 and c["val"] == 0)}
                chua_nhan = {c["par"] for c in g if c["cls"] == 2 and c["pst"] == 2 and c["ops"] == 0
                             and c["par"] in muc_tieu}
                for mid in sorted(set(buoc_dk) | chua_nhan):
                    if mid in buoc_dk:
                        c = buoc_dk[mid]
                        for n in muc_tieu[mid]["steps"]:
                            n = int(n)
                            if not OPS[c["ops"]](n, c["val"]):
                                continue
                            for kk, chon, tran, gn in di_tiep(groups, res, mid, i, sc):
                                lam[mid].setdefault(n, []).append(
                                    {"scene": sid, "kieu": chu[0], "idx": chu[1], "x": chu[2],
                                     "y": chu[3], "chon": chon, "tang": kk, "gia_nhap": gn,
                                     "boss": cap_boss(npc_lv, tran), "tran": bool(tran),
                                     "dk": dk_ra(g)})
                    elif any(c["cls"] == 2 and c["par"] == mid and c["pst"] == 2 and c["ops"] == 0
                             for c in g):
                        for kk, chon, tran, gn in di_tiep(groups, res, mid, i, sc):
                            nhan[mid].append({"scene": sid, "kieu": chu[0], "idx": chu[1],
                                              "x": chu[2], "y": chu[3], "chon": chon,
                                              "gia_nhap": gn,
                                              "boss": cap_boss(npc_lv, tran), "tran": bool(tran),
                                              "dk": dk_ra(g)})

    def cua_truoc(sid, mid, n, idx):
        """Cua su kien o cung scene: buoc n cham vao thi HIEN NPC idx (KQ t0 c3 par idx pst4),
        khong len buoc. Capture 10528 B2: 18506 cua 3 -> hien NPC 1 roi moi noi chuyen."""
        sc = scenes[sid]
        out = []
        for k in sorted(sc["doors"]):
            d = sc["doors"][k]
            for eno in d["events"]:
                for _i, g, res in nhom(sc["events"].get(eno, [])):
                    if any(c["cls"] == 2 and c["par"] == mid and c["pst"] == 1 and c["ops"] in OPS
                           and OPS[c["ops"]](n, c["val"]) for c in g) \
                            and any(t == 0 and c == 3 and p == idx and ps == 4
                                    for (t, c, p, ps, _v, _m) in res) \
                            and not tang(res, mid):
                        out.append({"cua": k, "x": d["x"], "y": d["y"]})
        return out

    sau = {}

    def do_sau(mid, dang=()):
        """Do sau trong chuoi giao quest (0 = dau chuoi). Vong lap -> cat."""
        if mid in sau:
            return sau[mid]
        if mid in dang or mid not in truoc:
            return 0
        d = max([do_sau(t, dang + (mid,)) + 1 for t in truoc[mid]] or [0])
        sau[mid] = d
        return d

    out = {key: {} for key in KINDS.values()}
    for mid, m in sorted(muc_tieu.items()):
        done = marks.get(str(mid + 1))
        if not done or not done.get("bitId"):
            continue
        steps = {}
        for ks, st in sorted(m["steps"].items(), key=lambda kv: int(kv[0])):
            n = int(ks)
            uv = lam[mid].get(n, [])
            dung = [u for u in uv if u["scene"] == st["endScene"] and (
                st["endEvKind"] == 0 or (u["kieu"] == ("npc" if st["endEvKind"] == 1 else "cua")
                                         and u["idx"] == st["endEvId"]))]
            ds = dung or uv
            s = {"desc": st["desc"].strip(), "team": bool(st["checkTeam"]),
                 "can": [{"kind": c["kind"], "id": c["id"], "count": c["count"], "scene": c["scene"]}
                         for c in st["conds"] if c["kind"]]}
            if ds:
                best = sorted(ds, key=lambda u: (u["tran"], u["chon"]))[0]
                d = {k: best[k] for k in ("scene", "kieu", "idx", "x", "y", "chon", "tran", "boss", "dk",
                                          "gia_nhap")}
                if best in dung and (st["endX"] or st["endY"]):
                    # Toa do DUNG BAM = diem dan duong cua client (MarkManager.Navigation di toi
                    # endPosition roi moi tu bam NPC), khong phai chan NPC: capture 10324 B1 client
                    # bam NPC 2 tu (744,369), NPC dung (830,360).
                    d["x"], d["y"] = st["endX"], st["endY"]
                if d["kieu"] == "npc":
                    d["truoc"] = cua_truoc(d["scene"], mid, n, d["idx"])
                d["chon_map"] = bang_chon(scenes[d["scene"]], d["kieu"], d["idx"], mid)
                s.update(d)
                lay = [u for c in s["can"] if c["kind"] == 1
                       for u in lay_npc(scenes, npc_lv, mid, n, c["id"], c["scene"])]
                if lay:
                    s["lay_npc"] = lay             # di lay NPC truoc khi lam buoc (vd ngua 10023)
                li = [u for c in st["conds"] if c["kind"] == 3
                      for u in [lay_item(scenes, mid, c, npc_lv)] if u]
                if li:
                    s["lay_item"] = li             # cho lay item client dan duong (vd thit xay 12288 B4)
                # DK `cls7 par6 pst3 ops5 val=npcId` = NPC do phai O NHA TRO (12290 B7 thoai 53107
                # "hãy gửi Cửu Sởi vào Nhà Trọ", user 10/10 xac nhan) -> gui vao truoc khi lam buoc.
                tro = [c[4] for c in d["dk"] if list(c[:4]) == [7, 6, 3, 5]]
                if tro:
                    ch = nha_tro(scenes, d["scene"])
                    if ch:
                        s["cat_tro"] = [dict(ch, npc=v) for v in tro]
            else:
                s["thieu"] = True                  # data khong co su kien lam buoc nay
            steps[str(n)] = s
        # cho nhan: bo trung (cung scene/chu/chon)
        seen, ds = set(), []
        for u in nhan[mid]:
            key = (u["scene"], u["kieu"], u["idx"], tuple(u["chon"]))
            if key not in seen:
                seen.add(key)
                u["chon_map"] = bang_chon(scenes[u["scene"]], u["kieu"], u["idx"], mid)
                ds.append(u)
        tran = any(s.get("tran") or s["team"] for s in steps.values()) or any(u["tran"] for u in ds)
        out[KINDS[m["kind"]]][str(mid)] = {
            "id": mid, "name": m["name"], "kind": m["kind"], "bit": done["bitId"], "tran": tran,
            "thu_tu": do_sau(mid), "truoc": sorted(truoc[mid]),
            "nhan": ds, "steps": steps}

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    for key, qs in out.items():
        n_buoc = sum(len(q["steps"]) for q in qs.values())
        n_thieu = sum(1 for q in qs.values() for s in q["steps"].values() if s.get("thieu"))
        print("%s: %d quest, %d co cho nhan, %d buoc (%d thieu), %d quest co tran" % (
            key, len(qs), sum(1 for q in qs.values() if q["nhan"]), n_buoc, n_thieu,
            sum(1 for q in qs.values() if q["tran"])))
    print("->", OUT, os.path.getsize(OUT), "byte")


if __name__ == "__main__":
    main()
