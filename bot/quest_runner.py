"""Mode "Lam quest": chu party lam chuoi quest, cac acc khac trong party ho tro.

Data: quests.json (tools/build_quests.py <- marks.json <- .dat client, xem KNOWLEDGE.md muc
"NHIEM VU (Mark)"). Moi quest: `id` = ma CHAN (mission dang lam trong 0x18 sub06), `bit` = co DA
XONG (`client.mark_flag_get`).

Luat user chot 03/10/2026 (documents/QUEST_CHUYEN_SINH.md):
  - luon chay theo party, user CHI DINH chu party (khong mac dinh slot 0)
  - chu party xong het chuoi -> chi dinh acc DAU TIEN (theo thu tu danh sach) chua xong lam chu
  - ca party xong het -> thoat game
Quest `gainWay = 0` (do duoc tu data ca 8 quest Cu Thu): chi NGUOI KICH HOAT duoc tinh, member
di theo khong xong quest -> bat buoc xoay vong chu party.
"""
from __future__ import annotations

import time

_quests = None


def _load_all():
    global _quests
    if _quests is None:
        try:
            from .client import _load_json_data_file
            _quests = _load_json_data_file("quests.json") or {}
        except Exception:
            _quests = {}
    return _quests


def chuoi(key):
    """Chuoi quest KICH BAN (vd 'cs1_cu_thu'), None = khong co.

    Muc chinh tuyen (co `nguon`, data o main_quests.json) KHONG tra ve o day: bo chay CS1 doc
    `ch["quests"]` -> lo routing sot thi CS1 chi thay "khong co chuoi" va dung yen, khong hieu nham
    thanh "xong het -> thoat game"."""
    ch = _load_all().get(key or "")
    return None if (ch and ch.get("nguon")) else ch


def danh_sach_chuoi():
    """[(key, label)] cho GUI."""
    return [(k, v.get("label", k)) for k, v in _load_all().items()]


def da_xong(client, ch):
    """{quest_id: True/False} hoac None khi acc CHUA NHAN co nhiem vu (vua login).

    None phai duoc coi la "chua biet", KHONG phai "chua xong" - doan bua la xoay chu party oan.
    """
    if client is None or not ch:
        return None
    if not getattr(client, "_mark_flags_loaded", False) or not getattr(client, "mark_flags", None):
        return None
    return {int(q["id"]): bool(client.mark_flag_get(int(q["bit"]))) for q in ch["quests"]}


def xong_het(client, ch):
    """True = xong ca chuoi, False = con quest, None = chua biet."""
    st = da_xong(client, ch)
    if st is None:
        return None
    return all(st.values())


def chon_chu_party(thu_tu, trang_thai, chu_hien_tai):
    """Quyet dinh chu party cho mode quest.

    thu_tu      : username theo thu tu danh sach user dat
    trang_thai  : {username: True (xong het) / False (con quest) / None (chua biet)}
    Tra (hanh_dong, username):
      ("giu", chu)   chu hien tai con quest -> lam tiep
      ("cho", None)  chua du thong tin de quyet
      ("doi", u)     chu xong het -> chi dinh u (acc dau tien con quest)
      ("thoat", None) ca party xong het
    """
    cur = trang_thai.get(chu_hien_tai)
    if cur is False:
        return ("giu", chu_hien_tai)
    con = [u for u in thu_tu if u != chu_hien_tai and trang_thai.get(u) is False]
    if con:
        # Chu chua biet (dang login) ma da co acc chac chan con quest: van CHO chu - chua biet
        # khong co nghia la xong.
        return ("cho", None) if cur is None else ("doi", con[0])
    if cur is None or any(trang_thai.get(u) is None for u in thu_tu):
        return ("cho", None)
    return ("thoat", None)


def quest_tiep_theo(client, ch):
    """(quest, step) chu party lam tiep. step = None khi chua nhan quest.

    Uu tien quest DANG LAM (co trong `mission_steps` server gui o 0x18 sub06) - lam tiep tu dung
    buoc server bao. Khong co thi lay quest dau tien chua xong MA DA CO KICH BAN (quest chua capture
    thi khong lam - chon sai ma la server ngat ket noi). (None, None) = khong con gi lam duoc.
    """
    st = da_xong(client, ch)
    if st is None:
        return (None, None)
    steps = getattr(client, "mission_steps", None) or {}
    for q in ch["quests"]:
        if not st.get(int(q["id"])) and int(q["id"]) in steps:
            return (q, int(steps[int(q["id"])]))
    for q in ch["quests"]:
        if not st.get(int(q["id"])) and q.get("kich_ban"):
            return (q, None)
    return (None, None)


def con_thieu_kich_ban(client, ch):
    """Ten cac quest chua xong ma CHUA CO kich ban (cho user capture tiep)."""
    st = da_xong(client, ch) or {}
    return [q["name"] for q in ch["quests"]
            if not st.get(int(q["id"])) and not q.get("kich_ban")]


def _diem(q, step):
    """Diem can toi cho buoc nay: dict scene/x/y/kieu/idx/chon/truoc, None = khong lam duoc."""
    if step is None:
        n = q.get("nhan_tai")
        if not n:
            return None
        # Nhan quest co the qua NPC hoac CUA AN (capture 10328: cua 4 o Dong Bach Son).
        kieu, idx = ("cua", n["cua"]) if n.get("cua") else ("npc", n["npc"])
        return {"scene": n["scene"], "x": n["x"], "y": n["y"], "kieu": kieu, "idx": idx,
                "chon": list(n.get("chon") or ()), "truoc": [], "ten": "nhan quest"}
    s = (q.get("steps") or {}).get(str(step))
    if not s:
        return None
    if s.get("ev_kind") in (1, 2):
        kieu, idx = ("npc" if s["ev_kind"] == 1 else "cua"), s["ev_id"]
    elif s.get("cua"):
        # ev_kind 0 = data chi ghi toa do. Capture 10324: do la CUA SU KIEN AN o dung toa do,
        # so cua lay tu capture (kich ban `cua`).
        kieu, idx = "cua", s["cua"]
    else:
        cua = _cua_cung_cho(q, s)
        if cua is None:
            return None      # chua capture buoc nay
        kieu, idx = "cua", cua
    return {"scene": s["scene"], "x": s["x"], "y": s["y"], "kieu": kieu, "idx": idx,
            "chon": list(s.get("chon") or ()), "truoc": list(s.get("truoc") or ()),
            "ten": "buoc %s" % step}


def _cua_cung_cho(q, s):
    """Buoc GOP (binh thuong server lam luon trong su kien buoc truoc) ma char lo KET o day: dung
    lai cua da co kich ban cua buoc khac CUNG QUEST, CUNG map + toa do.

    [nghi - chua capture] Ca that party 13, 04/10: su kien B1 Phan No Cua Bien (cua 2, Bot Hai) bi
    huy giua chung luc server bao len buoc 2 -> ket buoc 2 (data: ev_kind 0 tai DUNG (2207,282) cua
    B1) -> ca party dung im ~30 phut. Cham cua khong co su kien thi server chi tra `S:020-008`
    kind 0x23 (vo hai, capture 10528); server bat CHON thi `quest_hoi_thoai` dung, khong doan.
    """
    for k, s2 in (q.get("steps") or {}).items():
        if s2 is s or not s2.get("cua"):
            continue
        if (int(s2["scene"]), int(s2["x"]), int(s2["y"])) == (int(s["scene"]), int(s["x"]),
                                                              int(s["y"])):
            return int(s2["cua"])
    return None


def diem_ke_tiep(client, ch):
    """(quest, step, diem) chu party sap lam; diem = None khi khong co gi lam duoc."""
    q, step = quest_tiep_theo(client, ch)
    if q is None:
        return (None, None, None)
    return (q, step, _diem(q, step))


def dang_su_kien(client):
    """Worker chua nhan xong ket qua hoi thoai; khong bao gom di bo/cho retry.

    P40 05/10 00:57:07: het=True nhung worker chua doc -> doi chu huy no truoc khi tra xong.
    quest_hoi_thoai tu xoa _qev trong finally sau khi da chon ket qua.
    """
    return getattr(client, "_qev", None) is not None


def _toi(client, scene, x, y, abort, log):
    """Di bo toi (x, y) TRONG map `scene`. Chuyen map KHONG lam o day: engine da dua ca doi toi map
    nay bang lenh "DI MAP" co san (run_party_digioi `_quest_den_dich`)."""
    label = getattr(client, "_label", "?")
    if int(getattr(client, "current_map", 0) or 0) != int(scene):
        if log is not None:
            log.info("[%s] QUEST: chua o map %s (dang %s) -> cho lenh DI MAP dua doi toi", label,
                     scene, getattr(client, "current_map", None))
        return False
    if abort is not None and abort():
        return False
    arrived = client.navigate_to(int(x), int(y), abort=abort, flee=True)
    return (bool(arrived) and bool(client.running)
            and int(getattr(client, "current_map", 0) or 0) == int(scene)
            and not (abort is not None and abort()))


def lam_buoc(client, q, step, abort=None, log=None, du_party=None):
    """Lam mot buoc; chi thanh cong khi su kien da dong VA server bao len buoc/xong."""
    def dung_di():
        return (not client.running or (abort is not None and abort())
                or (du_party is not None and not du_party()))

    label = getattr(client, "_label", "?")
    d = _diem(q, step)
    if d is None or dung_di():
        return False
    if log is not None:
        log.info("[%s] QUEST: %s %s -> map %s (%s,%s) %s %s", label, q["name"], d["ten"],
                 d["scene"], d["x"], d["y"], d["kieu"], d["idx"])
    if not client._wait_combat_clear(idle=1.0, cap=120.0):
        return False
    if not _toi(client, d["scene"], d["x"], d["y"], dung_di, log):
        return False
    for t in d["truoc"]:
        # Cua su kien rieng cua quest (vd 18506 cua 3, Thai Ho buoc 2) - client that cham truoc NPC.
        if not _toi(client, d["scene"], t["x"], t["y"], dung_di, log) or dung_di():
            return False
        client.quest_kich_hoat("cua", int(t["cua"]))
        kq = client.quest_hoi_thoai(abort=abort, im_lang=15.0)
        if log is not None:
            log.info("[%s] QUEST: cham cua %s truoc -> %s", label, t["cua"], kq)
        if kq != "xong" or not _toi(client, d["scene"], d["x"], d["y"], dung_di, log):
            return False
    qid = int(q["id"])
    truoc = int((getattr(client, "mission_steps", None) or {}).get(qid, 0))
    # Review 04/10: roster co the tut ngay sau khi di toi, truoc nhip engine ke tiep.
    if dung_di():
        return False
    client.quest_kich_hoat(d["kieu"], d["idx"])
    kq = client.quest_hoi_thoai(chon=d["chon"], abort=abort)
    sau = int((getattr(client, "mission_steps", None) or {}).get(qid, 0))
    xong = bool(client.mark_flag_get(int(q["bit"])))
    ok = kq == "xong" and (xong or sau > truoc)
    sig = (qid, step)
    if ok:
        client._quest_khong_tien = None
    elif kq == "xong":
        # mhmmot 05/10 00:50..00:58: 15 lan thoai xong nhung buoc van 0. Khong doan ma chon.
        cu = getattr(client, "_quest_khong_tien", None)
        lan = cu[1] + 1 if cu and cu[0] == sig else 1
        client._quest_khong_tien = (sig, lan)
        if lan == 3 and log is not None:
            log.warning("[%s] QUEST: %s buoc %s - 3 lan hoi thoai xong nhung KHONG LEN BUOC; "
                        "DUNG THU LAI buoc nay. Chua biet dieu kien thieu/ly do server tu choi; "
                        "kiem tra trong game/capture, khoi dong lai acc de thu lai.", label,
                        q["name"], step)
    if log is not None:
        (log.info if ok else log.warning)(
            "[%s] QUEST: %s %s -> su kien %s, buoc %d -> %d%s", label, q["name"], d["ten"], kq,
            truoc, sau, " (XONG QUEST)" if xong else ("" if ok else " -> KHONG LEN BUOC"))
    return ok


def chay(client, key, abort=None, log=None, cho=30.0, du_party=None):
    """Chu party lam 1 nhip quest: lam mot buoc cua quest tiep theo.

    Khong lam duoc gi (chua nhan co, quest con lai chua co kich ban, buoc hong) -> log MOT lan roi
    dung yen `cho` giay. Khong tra ve ngay: viec chay xong ngay ma khong doi gi la engine giao lai
    moi giay (CORE_FLOW: "giao lai N lan lien tiep").
    """
    ch = chuoi(key)
    label = getattr(client, "_label", "?")
    if not ch:
        if log is not None:
            log.warning("[%s] QUEST: khong co chuoi quest '%s' trong quests.json", label, key)
        return False
    q, step = quest_tiep_theo(client, ch)
    if q is not None:
        try:
            client.ensure_pet_role("quest")
        except Exception:
            pass
        sig = (q["id"], step)
        cu = getattr(client, "_quest_khong_tien", None)
        bi_chan = cu is not None and cu[0] == sig and cu[1] >= 3
        if not bi_chan and lam_buoc(client, q, step, abort=abort, log=log, du_party=du_party):
            client._quest_hong = None
            return True
        if getattr(client, "_quest_hong", None) != sig:
            client._quest_hong = sig
            if log is not None:
                log.warning("[%s] QUEST: %s buoc %s CHUA lam duoc -> dung yen %.0fs roi thu lai",
                            label, q["name"], step, cho)
    else:
        thieu = con_thieu_kich_ban(client, ch)
        if thieu and getattr(client, "_quest_log_thieu", None) != tuple(thieu):
            client._quest_log_thieu = tuple(thieu)
            if log is not None:
                log.info("[%s] QUEST: con %d quest CHUA CO KICH BAN (cho capture): %s -> dung yen",
                         label, len(thieu), thieu)
    het = time.time() + float(cho)
    while time.time() < het:
        if abort is not None and abort():
            break
        time.sleep(0.5)
    return True


# ============================================================ CHINH TUYEN (sinh tu Eve.emg)
# documents/QUEST_CHINH_TUYEN.md. Data: main_quests.json (tools/crack_eve_quest.py). quests.json
# chi giu muc {"label", "nguon"} de GUI/APK hien chuoi (doc chung mot file, khong chep tay).
# NAC A (08/10): CHI DOC - tinh ke hoach quest trong so roi ghi log, KHONG gui goi nao.

_main = None
_MAX_VO_TUONG = 4        # Role.maxFollowNpc (Logic/Role.lua "最大跟隨武將數")


def _load_main():
    global _main
    if _main is None:
        try:
            from .client import _load_json_data_file
            _main = _load_json_data_file("main_quests.json") or {}
        except Exception:
            _main = {}
    return _main


def la_chinh_tuyen(key):
    """Chuoi sinh tu Eve.emg (muc quests.json co `nguon`), khong phai chuoi kich ban CS1."""
    ch = _load_all().get(key or "")
    return bool(ch and ch.get("nguon"))


def quest_chinh_tuyen(key):
    """{str(mid): quest} cua chuoi chinh tuyen, {} = khong co data."""
    return _load_main().get(key or "") or {}


def _cap_server(client):
    """Cap nhu server so (byte Lv trong vong chuyen sinh). `char_level` da +200 khi Turn>=3 (client
    RoleController.lua:4030) -> tru lai. [nghi] DK `cls7 pst1` la cap nay - chua doi chung."""
    lv = getattr(client, "char_level", None)
    if lv is None:
        return None
    return int(lv) - (200 if getattr(client, "char_turn3_element", None) in (7, 8) else 0)


_OPS = {1: lambda a, b: a < b, 2: lambda a, b: a > b, 3: lambda a, b: a <= b,
        4: lambda a, b: a >= b, 5: lambda a, b: a == b, 6: lambda a, b: a != b}


def danh_gia_dk(client, dk):
    """Danh gia nhom dieu kien server (`[cls, par, pst, ops, val]`, KNOWLEDGE.md "KICH BAN SERVER
    TRONG Eve.emg") tren trang thai acc: True / False / None (co dieu kien bot chua doc duoc)."""
    from .client import _load_mark_bitids
    steps = getattr(client, "mission_steps", None) or {}
    chua_biet = False
    for cls, par, pst, ops, val in dk:
        if cls == 0:
            continue
        if cls == 2 and pst == 1 and ops in _OPS:
            ok = _OPS[ops](int(steps.get(int(par), 0)), val)
        elif cls == 2 and pst == 2 and ops == 0:
            ok = int(steps.get(int(par), 0)) == 0
        elif cls == 2 and pst == 3 and ops in _OPS:
            bit = _load_mark_bitids().get(int(par))
            if not bit:
                chua_biet = True
                continue
            ok = _OPS[ops](1 if client.mark_flag_get(int(bit)) else 0, val)
        elif cls == 7 and pst == 1 and ops in _OPS:
            lv = _cap_server(client)
            if lv is None:
                chua_biet = True
                continue
            ok = _OPS[ops](lv, val)
        else:
            chua_biet = True
            continue
        if not ok:
            return False
    return None if chua_biet else True


def ma_chuoi_rieng():
    """Ma quest thuoc CHUOI KICH BAN rieng (quests.json co `quests`, vd `cs1_cu_thu` 8 Cu Thu):
    mode chinh tuyen KHONG dung vao - chung mang nhan [Chinh] nhung chay mode rieng (party).
    User 09/10: "Thuong khung loan vu la quest 8 cu thu" (10806 lot vao danh sach chinh tuyen)."""
    out = set()
    for k in _load_all():
        ch = chuoi(k)
        if isinstance(ch, dict):
            out |= {int(q["id"]) for q in ch.get("quests") or () if q.get("id")}
    return out


def ke_hoach_chinh_tuyen(client, key, toi_da=None, chi_so=True):
    """Ke hoach quest chinh tuyen cua MOT acc, None = chua nhan co nhiem vu (vua login).

    Tra {"dang": [(q, buoc)], "nhan": [(q, cho_nhan)], "chua_ro": [q], "se_lam": [(q, buoc|None,
    cho)], ...}: quest DANG LAM (mission_steps) truoc, roi quest nhan duoc ngay (dieu kien server
    dung het), ma nho truoc. Quest hay duoc server TU GIAO khi xong buoc cuoi quest truoc (12280
    B5 -> 12282) nen phan lon nam o "dang".

    chi_so=True (user chot 08/10 "tam thoi lam a"): CHI lam quest DANG CO trong so nhiem vu, xong
    thi server tu giao quest tiep - y nhu choi tay. Quest server cho nhan ngay (vd 10268 chi doi cap)
    van dem trong "nhan" de log, KHONG dua vao se_lam.

    THU TU (user 09/10): [Chinh] trong so truoc, het (hoac ket) thi toi [Huong Dan] trong so; Huong
    Dan hay chinh la cho server GIAO [Chinh] tiep (12290 B5 Cuu Soi chon 30 -> giao 10015 + tam xoa
    12290) -> nhip sau [Chinh] moi len dau lai.
    """
    qs = quest_chinh_tuyen(key)
    if client is None or not qs:
        return None
    if not getattr(client, "_mark_flags_loaded", False) or not getattr(client, "mark_flags", None):
        return None
    steps = getattr(client, "mission_steps", None) or {}
    dang, nhan, chua_ro, xong, rieng = [], [], [], [], []
    bo = ma_chuoi_rieng()
    # Thu tu COT TRUYEN (`thu_tu` = do sau chuoi giao quest, tools/crack_eve_quest.py), roi ma.
    for mid in sorted(qs, key=lambda k: (int(qs[k].get("thu_tu") or 0), int(k))):
        q = qs[mid]
        if int(mid) in bo:
            if int(steps.get(int(mid), 0)) > 0:
                rieng.append((q, int(steps[int(mid)])))
            continue
        if client.mark_flag_get(int(q["bit"])):
            xong.append(q)
            continue
        b = int(steps.get(int(mid), 0))
        if b > 0:
            dang.append((q, b))
            continue
        kq = [(danh_gia_dk(client, u["dk"]), u) for u in q.get("nhan") or ()]
        duoc = [u for ok, u in kq if ok is True]
        if duoc:
            nhan.append((q, duoc[0]))
        elif any(ok is None for ok, _u in kq):
            chua_ro.append(q)
    # Quest DANG CO: dung thu tu so nhiem vu client (MarkManager.SortShowMission: kind roi ma).
    dang.sort(key=lambda x: (int(x[0].get("kind") or 1), int(x[0]["id"])))
    hd = []
    if key == "chinh_tuyen":
        for mid, q in quest_chinh_tuyen("huong_dan").items():
            b = int(steps.get(int(mid), 0))
            if b > 0 and int(mid) not in bo and not client.mark_flag_get(int(q["bit"])):
                hd.append((q, b))
        hd.sort(key=lambda x: int(x[0]["id"]))
    se_lam = [(q, b, (q["steps"].get(str(b)) or {})) for q, b in dang + hd]
    if not chi_so:
        se_lam += [(q, None, u) for q, u in nhan]
    return {"dang": dang, "huong_dan": hd, "nhan": nhan, "chua_ro": chua_ro, "xong": xong,
            "rieng": rieng, "tong": len(qs) - len(bo & {int(k) for k in qs}),
            "cap": _cap_server(client), "se_lam": se_lam[:toi_da] if toi_da else se_lam}


def _mo_ta(q, buoc, d):
    """Mot dong mo ta viec cua quest cho log ke hoach."""
    if d.get("thieu"):
        cach = "KHONG CO su kien lam buoc nay trong data"
    else:
        cach = "map %s %s %s (%s,%s)" % (d.get("scene"), d.get("kieu"), d.get("idx"),
                                         d.get("x"), d.get("y"))
        if d.get("chon"):
            cach += " chon %s" % d["chon"]
        if d.get("truoc"):
            cach += " cham cua %s truoc" % [t["cua"] for t in d["truoc"]]
        if d.get("tran"):
            cach += " | CO TRAN boss lv%s" % d.get("boss")
        if d.get("gia_nhap"):
            cach += " | %d NPC GIA NHAP (can o vo tuong)" % d["gia_nhap"]
        for u in d.get("lay_item") or ():
            cach += " | LAY ITEM %s x%s: map %s %s (%s,%s)%s" % (
                u["item"], u["count"], u["scene"],
                "%s %s" % (u["kieu"], u["idx"]) if u.get("bam") else
                ("danh quai quanh %s %s" % (u["kieu"], u["idx"]) if u.get("kieu") else
                 ("dao mo %s (x %s-%s, y %s-%s)" % (u["mo"]["id"], u["mo"]["x0"], u["mo"]["x1"],
                                                     u["mo"]["y0"], u["mo"]["y1"])
                  if u.get("mo") else ("di lai danh quai quanh diem" if u.get("di_lai")
                                       else "danh quai quanh diem"))),
                u["x"], u["y"], " CO TRAN" if u.get("tran") else "")
        for l in d.get("lay_npc") or ():
            cach += " | LAY NPC %s truoc: map %s %s %s (%s,%s)%s" % (
                l["npc"], l["scene"], l["kieu"], l["idx"], l["x"], l["y"],
                " chon %s" % l["chon"] if l.get("chon") else "")
        for t in d.get("cat_tro") or ():
            cach += " | GUI NPC %s vao nha tro truoc: map %s %s %s (%s,%s) chon %s" % (
                t["npc"], t["scene"], t["kieu"], t["idx"], t["x"], t["y"], t.get("chon_map"))
        if d.get("can"):
            cach += " | CAN %s" % ["%s:%s x%s" % ({1: "dan NPC", 3: "item"}.get(c["kind"], c["kind"]),
                                                 c["id"], c["count"]) for c in d["can"]]
    viec = "nhan quest" if buoc is None else "buoc %s/%s" % (buoc, len(q["steps"]))
    loai = "PARTY" if q.get("tran") else "LE"
    nhom = {1: "Chinh", 2: "Huong Dan", 3: "Phu"}.get(int(q.get("kind") or 1), "?")
    return "%s %s (%s) [%s] %s -> %s" % (q["id"], q["name"], nhom, loai, viec, cach)


def _ds_mission(steps):
    """'id ten bN' moi mission server gui (0x18 sub06) - ten lay tu main_quests.json neu co."""
    ten = {}
    for ch in _load_main().values():
        for k, q in ch.items():
            ten[int(k)] = q["name"]
    return ", ".join("%s %s b%s" % (m, ten.get(int(m), "?"), b)
                     for m, b in sorted(steps.items())) or "-"


def _log_ke_hoach(client, kh, log, nhan_log="CHI DOC"):
    """Ghi ke hoach khi no DOI (khong lap moi nhip)."""
    label = getattr(client, "_label", "?")
    sig = tuple((q["id"], b) for q, b, _d in kh["se_lam"])
    if log is None or getattr(client, "_qct_log", None) == sig:
        return
    client._qct_log = sig
    log.info("[%s] QUEST CT (%s): cap %s | xong %d/%d | dang do %d | nhan duoc %d | "
             "chua danh gia duoc %d %s", label, nhan_log, kh["cap"], len(kh["xong"]), kh["tong"],
             len(kh["dang"]), len(kh["nhan"]), len(kh["chua_ro"]),
             [q["id"] for q in kh["chua_ro"][:8]])
    # Doi chieu voi so nhiem vu trong game (user 08/10 qg506: "xong 16" la nhung quest nao)
    log.info("[%s] QUEST CT   da xong: %s", label,
             ", ".join("%s %s" % (q["id"], q["name"]) for q in kh["xong"]) or "-")
    log.info("[%s] QUEST CT   mission dang co (moi loai): %s", label,
             _ds_mission(getattr(client, "mission_steps", None) or {}))
    for k_ch, nhan_game in (("phu_tuyen", "Phu"),):
        khac = quest_chinh_tuyen(k_ch)
        log.info("[%s] QUEST CT   [%s] dang co (CHUA LAM): %s", label, nhan_game, ", ".join(
            "%s %s b%s" % (m, khac[str(m)]["name"], b) for m, b in sorted(
                (getattr(client, "mission_steps", None) or {}).items()) if str(m) in khac)
            or "-")
    if kh.get("rieng"):
        log.info("[%s] QUEST CT   chuoi rieng (Cu Thu - mode party, KHONG lam o day): %s", label,
                 ", ".join("%s %s b%s" % (q["id"], q["name"], b) for q, b in kh["rieng"]))
    for i, (q, b, d) in enumerate(kh["se_lam"], 1):
        log.info("[%s] QUEST CT   %d. %s", label, i, _mo_ta(q, b, d))
    if not kh["se_lam"]:
        log.info("[%s] QUEST CT: so nhiem vu khong co quest [Chinh]/[Huong Dan] nao dang lam "
                 "(%d quest server cho nhan them - chua lam, user chon cach a)", label,
                 len(kh["nhan"]))


def _ngu(cho, abort):
    het = time.time() + float(cho)
    while time.time() < het:
        if abort is not None and abort():
            break
        time.sleep(0.5)


def chay_chinh_tuyen_doc(client, key, abort=None, log=None, cho=30.0):
    """NAC A: tinh ke hoach roi ghi log khi ke hoach DOI, khong gui goi nao; dung yen `cho` giay."""
    label = getattr(client, "_label", "?")
    kh = ke_hoach_chinh_tuyen(client, key)
    if kh is None:
        if log is not None and getattr(client, "_qct_log", None) != "cho":
            client._qct_log = "cho"
            log.info("[%s] QUEST CT: chua nhan co nhiem vu -> cho", label)
        cho = 2.0
    else:
        _log_ke_hoach(client, kh, log)
    _ngu(cho, abort)
    return True


# ------------------------------------------------------------ NAC B: lam that, DI LE (08/10)
_solo = None


def _solo_cfg():
    global _solo
    if _solo is None:
        try:
            from .client import _load_json_data_file
            _solo = _load_json_data_file("quest_solo.json") or {}
        except Exception:
            _solo = {}
    return _solo


def ds_solo(key):
    """Quest CO TRAN user cho phep di le (quest_solo.json, danh dau tay). Quest khong co tran tu di
    le, khong can ghi. User 08/10: "Dao Vien Ket Nghia danh solo toan bo"."""
    return {int(x) for x in (_solo_cfg().get(key or "") or [])}


def solo_het():
    """`"solo_het": true` trong quest_solo.json = MOI quest di le (user 09/10: "nhung quest dau nay
    cu cho solo het, den khi nao t bao di party thi luc do moi can")."""
    return bool(_solo_cfg().get("solo_het"))


def _so_item(client, tid):
    return sum(int(v[1]) for v in (getattr(client, "bag_slots", None) or {}).values()
               if v and int(v[0]) == int(tid))


def _dang_theo(client, npc_id):
    """NPC npc_id dang di theo acc khong: True/False, None = chua biet (chua nhan danh sach pet)."""
    fn = getattr(client, "follow_npc", None)
    if fn is None:
        return None
    return int(npc_id) in {int(v) for v in fn.values()}


def _can_lay(client, d):
    """Cac cho DUA NPC (`lay_npc`) ma NPC do CHUA di theo -> phai di lay truoc khi lam buoc.
    Chua biet (None) cung tinh la can lay: ly_do_ket chan "chua biet so o" truoc roi."""
    return [l for l in d.get("lay_npc") or () if not _dang_theo(client, l["npc"])]


def _can_item(client, d):
    """Cho LAY ITEM (`lay_item`) ma trong tui CHUA DU so luong."""
    return [u for u in d.get("lay_item") or () if _so_item(client, u["item"]) < int(u["count"])]


def ly_do_ket(client, key, q, b, d):
    """None = lam duoc buoc nay; chuoi = ly do DUNG YEN (len "Chu y").

    `can` kind 1 (NPC di theo, vd Truong Phi/Quan Vu o 10001 B4-B6) KHONG chan: NPC do su kien buoc
    truoc cho di theo; chua theo ma co cho dua (`lay_npc`, vd ngua 10023) thi lam_buoc_ct di lay
    truoc - chi can them o vo tuong trong; mat thi chan "3 lan khong len buoc" bat. Kind 3 (item) thieu thi chan - bot
    chua biet lay item o dau (user 08/10: "dung yen, ban thong bao vao Chu y").
    """
    if d.get("thieu"):
        return "bước %s/%s không có sự kiện trong data" % (b, len(q["steps"]))
    for u in _can_item(client, d):
        if _HOP.get(int(u["item"])) and _o_nguyen_lieu(client, _HOP[int(u["item"])]):
            continue                     # hop tu nguyen lieu trong tui, khong can cuoc
        if _mo_khoang(u) and not _co_cuoc(client):
            return ("cần Cuốc để đào khoáng lấy item %s (không đeo, trong túi cũng không có)"
                    % u["item"])
    co_cho = {int(u["item"]) for u in d.get("lay_item") or ()}
    for c in d.get("can") or ():
        if (int(c["kind"]) == 3 and int(c["id"]) not in co_cho
                and _so_item(client, c["id"]) < max(1, int(c["count"]))):
            return "cần item %s x%s (đang có %s) - client không chỉ chỗ lấy" % (
                c["id"], c["count"], _so_item(client, c["id"]))
    # + NPC phai di lay truoc (10023 B1: ngua 18005 - log p52 09/10 Ma Phu khong nhan vi chua co ngua)
    gn = int(d.get("gia_nhap") or 0) + len(_can_lay(client, d))
    if gn:
        # NPC XIN GIA NHAP chiem o vo tuong: client chi nhan khi < Role.maxFollowNpc (= 4)
        # (EventHandler.lua "要求加入玩家"). User 08/10: "quest nay can slot trong cua pet".
        fs = getattr(client, "follow_slots", None)
        if fs is None:
            return "chưa biết số ô võ tướng (chưa nhận danh sách pet) - bước này có NPC gia nhập"
        if len(fs) + gn > _MAX_VO_TUONG:
            return "cần %d ô võ tướng trống để NPC gia nhập (đang dùng %d/%d) - cất bớt pet" % (
                gn, len(fs), _MAX_VO_TUONG)
    if q.get("tran") and not solo_het() and int(q["id"]) not in ds_solo(key):
        return "quest có trận - cần party (chưa làm; solo được thì thêm vào quest_solo.json)"
    cu = getattr(client, "_qct_khong_tien", None)
    if cu and cu[0] == (int(q["id"]), b) and cu[1] >= 3:
        if cu[2] == "im_lang":
            # Log p52 09/10: su kien bi huy giua tran -> server LO moi lan bam NPC (vet=[]).
            return ("bấm NPC 3 lần server không phản hồi (nghi còn kẹt sự kiện cũ) - khởi động "
                    "lại acc")
        if cu[2] == "item_khong_co":
            return ("bấm chỗ lấy item %s 3 lần nhưng không nhận được item - khởi động lại acc để "
                    "thử lại" % ", ".join(str(u["item"]) for u in _can_item(client, d)))
        if cu[2] == "nha_tro":
            return ("gửi NPC %s vào nhà trọ 3 lần không được (nhà trọ đầy?) - cất bớt rồi khởi "
                    "động lại acc" % ", ".join(str(t["npc"]) for t in d.get("cat_tro") or ()))
        if cu[2] == "npc_khong_theo":
            return ("nói chuyện với NPC %s 3 lần nhưng NPC không đi theo - khởi động lại acc để "
                    "thử lại" % ", ".join(str(l["npc"]) for l in _can_lay(client, d)))
        return "3 lần làm xong nhưng không lên bước (%s) - khởi động lại acc để thử lại" % cu[2]
    return None


def _di_toi(client, scene, x, y, abort):
    """Di LE toi (x, y) map `scene`: khac map -> `follow_smart_route` (tele thanh gan nhat + di bo
    qua cong da xac minh); cung map -> navigate_to. Gap quai doc duong -> BO CHAY (user 08/10)."""
    if int(getattr(client, "current_map", 0) or 0) != int(scene):
        client.follow_smart_route(int(scene), (int(x), int(y)), abort=abort, flee=True)
    else:
        client.navigate_to(int(x), int(y), abort=abort, flee=True)
    return (bool(client.running) and int(getattr(client, "current_map", 0) or 0) == int(scene)
            and not (abort is not None and abort()))


_VT_VU_KHI = 3            # fitType vu khi (Cuoc `ft` = 3)
_DANH_KHOANG_GIAY = 120.0  # co "danh quai khoang" TU HET HAN - roi pha dao mo la quay ve bo chay


def _la_cuoc(tid):
    from .client import _load_gamedata_items
    return int((_load_gamedata_items().get(int(tid or 0)) or {}).get("sa") or 0) == 8


def _cuoc_trong_tui(client):
    return sorted(int(sl) for sl, r in (getattr(client, "bag_slots", None) or {}).items()
                  if r and int(r[1]) > 0 and _la_cuoc(r[0]))


def _mo_khoang(u):
    """Vung mo co quai KHOANG (NPC kind 16) -> phai deo Cuoc + khong bo chay."""
    from . import config
    ids = getattr(config, "MINERAL_NPC_IDS", None) or ()
    return bool(u.get("mo")) and any(int(n) in ids for n in u["mo"].get("quai") or ())


def _co_cuoc(client):
    """Char dang deo Cuoc hoac trong tui con Cuoc."""
    return (_la_cuoc((getattr(client, "equip_by_fit", None) or {}).get(_VT_VU_KHI))
            or bool(_cuoc_trong_tui(client)))


def _deo_cuoc(client, log=None):
    """Deo Cuoc cho CHAR + PET XUAT CHIEN (thoai 11116: "Khi đào khoáng ngươi và võ tướng phải
    trang bị Cuốc"; 11112 cho 2 cai). Nho vu khi cu de `_thao_cuoc` deo lai. True = char co Cuoc."""
    label = getattr(client, "_label", "?")
    cu = getattr(client, "_qct_vk_cu", None)
    if cu is None:
        cu = client._qct_vk_cu = {}
    ai = [(0, getattr(client, "equip_by_fit", None) or {})]
    pet = getattr(client, "active_pet_slot", None)
    if pet:
        ai.append((int(pet), (getattr(client, "pet_equip_by_fit", None) or {}).get(int(pet)) or {}))
    for follow, bang in ai:
        dang = bang.get(_VT_VU_KHI)
        if _la_cuoc(dang):
            continue
        tui = _cuoc_trong_tui(client)
        if not tui:
            if log is not None and follow:
                log.info("[%s] QUEST CT: het Cuoc trong tui -> pet #%d danh khong cuoc", label,
                         follow)
            continue
        cu.setdefault(follow, int(dang or 0))
        if follow:
            client.equip_pet_item(follow, tui[0])
        else:
            client.equip_item(tui[0])
        if log is not None:
            log.info("[%s] QUEST CT: deo Cuoc (o tui %d) cho %s, vu khi cu %s", label, tui[0],
                     "pet #%d" % follow if follow else "nhan vat", dang)
        time.sleep(1.0)
    return _la_cuoc((getattr(client, "equip_by_fit", None) or {}).get(_VT_VU_KHI))


def _thao_cuoc(client, log=None):
    """Deo lai vu khi cu (Cuoc tu ve tui); khong co vu khi cu thi coi Cuoc ra."""
    cu = getattr(client, "_qct_vk_cu", None) or {}
    label = getattr(client, "_label", "?")
    for follow, tid in sorted(cu.items()):
        bang = ((getattr(client, "pet_equip_by_fit", None) or {}).get(follow) or {}) if follow \
            else (getattr(client, "equip_by_fit", None) or {})
        if not _la_cuoc(bang.get(_VT_VU_KHI)):
            continue
        o = [int(sl) for sl, r in (getattr(client, "bag_slots", None) or {}).items()
             if r and int(r[0]) == int(tid) and int(r[1]) > 0] if tid else []
        if o:
            (client.equip_pet_item(follow, o[0]) if follow else client.equip_item(o[0]))
        else:
            client.unequip_item(_VT_VU_KHI, follow=follow)
        if log is not None:
            log.info("[%s] QUEST CT: thao Cuoc %s -> %s", label,
                     "pet #%d" % follow if follow else "nhan vat",
                     "deo lai vu khi cu %s" % tid if o else "coi ra tui")
        time.sleep(1.0)
    client._qct_vk_cu = None
    st = getattr(client, "state", None)
    if st is not None:
        st.danh_khoang_den = 0.0


def _diem_mo(mo):
    """Diem di lai TRONG vung mo (lui vao 60px tu mep) - dung yen thi server khong kich hoat."""
    x0, y0, x1, y1 = int(mo["x0"]) + 60, int(mo["y0"]) + 60, int(mo["x1"]) - 60, int(mo["y1"]) - 60
    if x1 <= x0:
        x0 = x1 = (int(mo["x0"]) + int(mo["x1"])) // 2
    if y1 <= y0:
        y0 = y1 = (int(mo["y0"]) + int(mo["y1"])) // 2
    return [((x0 + x1) // 2, (y0 + y1) // 2), (x0, y0), (x1, y0), (x1, y1), (x0, y1)]


_DI_LAI_PX = 120   # buoc di lai quanh diem farm khong co quai lao vao


def _diem_quanh(x, y):
    """Vong di lai quanh diem farm: diem goc + 4 huong, lech `_DI_LAI_PX`."""
    x, y, d = int(x), int(y), _DI_LAI_PX
    return [(x, y), (max(20, x - d), y), (x, max(20, y - d)), (x + d, y), (x, y + d)]


_GAN_DIEM_FARM_PX = 200   # da dung trong ban kinh nay quanh diem danh quai -> khong goi lai _di_toi


def _dang_o_diem_farm(client, u):
    """Da dung o diem danh quai (cung map, cach <= `_GAN_DIEM_FARM_PX`) -> True.

    `lam_buoc_ct` lap lai ~75s/lan, moi lan `_di_toi` (flee=True, luat "gap quai doc duong -> bo
    chay" user 08/10) toi CHINH diem dang dung -> quai cham dung luc do bi BO CHAY. Log p52 10/10
    Vuba 11180 map 12861 (770,1610): 12/69 tran bo chay, 11/12 ngay sau `smart path (770, 1610) ->
    (770,1610)`. Chi ap cho diem DANH QUAI (khong `bam` NPC, khong `mo` dao) - hai loai kia giu
    nguyen duong cu."""
    if u.get("bam") or u.get("mo"):
        return False
    if int(getattr(client, "current_map", 0) or 0) != int(u["scene"]):
        return False
    p = getattr(client, "pos", None)
    if not p:
        return False
    dx, dy = int(p[0]) - int(u["x"]), int(p[1]) - int(u["y"])
    return dx * dx + dy * dy <= _GAN_DIEM_FARM_PX * _GAN_DIEM_FARM_PX


def _cho_item(client, u, giay):
    han = time.time() + giay
    while _so_item(client, u["item"]) < int(u["count"]) and time.time() < han and client.running:
        time.sleep(0.2)          # goi them item vao tui toi sau khi su kien/tran dong
    return _so_item(client, u["item"]) >= int(u["count"])


# CONG THUC HOP item quest: dich <- 2 cai nguyen lieu. Client KHONG co bang hop (Compound.Dat bi
# comment trong DataManager.lua, server tu tinh) -> chi ghi cong thuc DA CHOT:
#   44042 Vo Danh Tich Thach <- 2 x 37407 Vo Danh Tich Sa: quest 11120 (nhan quest server dua 35 Tich
#   Sa; thoai 53066 "...hợp thành Vô Danh Tích Thạch, trong quá trình hợp thành có thể thất bại!"),
#   user 10/10 xac nhan "2 Tich Sa -> 1 Tich Thach".
_HOP = {44042: 37407}


def _o_nguyen_lieu(client, tid):
    """(o1, o2) de hop 2 cai `tid`: mot o >= 2 cai thi hop voi chinh no (user xac nhan 25/08 hop
    cung o duoc), khong thi 2 o khac nhau. None = khong du 2 cai."""
    o = sorted((int(sl), int(r[1])) for sl, r in (getattr(client, "bag_slots", None) or {}).items()
               if r and int(r[0]) == int(tid) and int(r[1]) > 0 and int(sl) <= 0xFF)
    for sl, n in o:
        if n >= 2:
            return sl, sl
    return (o[0][0], o[1][0]) if len(o) >= 2 else None


def _hop_item(client, u, nl, abort, log, toi_da=10):
    """Hop 2 `nl` -> `u["item"]` toi khi du (hop co the THAT BAI -> hop tiep). True = du item."""
    label = getattr(client, "_label", "?")
    for lan in range(1, toi_da + 1):
        if _so_item(client, u["item"]) >= int(u["count"]):
            break
        if not client.running or (abort is not None and abort()):
            return False
        o = _o_nguyen_lieu(client, nl)
        if o is None:
            break
        truoc_nl = _so_item(client, nl)
        client.combine_slots(*o)
        han = time.time() + 3.0
        while (time.time() < han and client.running and _so_item(client, nl) == truoc_nl
               and _so_item(client, u["item"]) < int(u["count"])):
            time.sleep(0.2)
        if log is not None:
            log.info("[%s] QUEST CT: hop 2 x %s (o %s+%s) -> %s lan %d: tui co %s x%s, con %s x%s",
                     label, nl, o[0], o[1], u["item"], lan, u["item"], _so_item(client, u["item"]),
                     nl, _so_item(client, nl))
    return _so_item(client, u["item"]) >= int(u["count"])


def _lay_item(client, sig, u, abort, log):
    """Lay item y client TU DAN DUONG (`MarkManager.Navigation`). True = du item.

    - cho la NPC/cua co su kien CLICK (`bam`): bam + hoi thoai (danh tran neu co). Su kien co
      tran -> danh lai toi khi ra item (user 09/10 "danh khi nao ra thi thoi"); khong tran ma
      3 lan khong ra item -> "Chu y".
    - con lai (diem tren map / quai chi cham-server nhu Banh Bao Thit 12808 NPC 13): toi diem,
      bat lai hop may (`combat_ready`, y train) roi DUNG DANH quai gap phai, khong bo chay.
    """
    label = getattr(client, "_label", "?")
    nl = _HOP.get(int(u["item"]))
    if nl and _o_nguyen_lieu(client, nl):
        # Co cong thuc + du nguyen lieu trong tui -> HOP tai cho, khong chay di (client chi ve map mo
        # cho 11120 nhung item phai hop). Het nguyen lieu thi xuong duoi: di lay theo client chi.
        return _hop_item(client, u, nl, abort, log)
    if int(getattr(client, "current_map", 0) or 0) != int(u["scene"]):
        client._qct_farm = None          # vua chet ve thanh / bi keo di -> toi lai phai bat lai hop may
    if _dang_o_diem_farm(client, u):
        pass                             # DA dung o diem quai -> khong "di toi" kem BO CHAY
    elif not _di_toi(client, u["scene"], u["x"], u["y"], abort):
        return False
    client.flee_mode = False
    if u.get("bam"):
        client.quest_kich_hoat(u["kieu"], int(u["idx"]))
        kq = client.quest_hoi_thoai(chon=dict(u.get("chon_map") or {}), abort=abort)
        du = _cho_item(client, u, 3.0)
        if log is not None:
            (log.info if du else log.warning)(
                "[%s] QUEST CT: lay item %s (map %s %s %s) -> su kien %s, tui co %s/%s", label,
                u["item"], u["scene"], u["kieu"], u["idx"], kq, _so_item(client, u["item"]),
                u["count"])
        if not du and kq != "dung" and not (kq == "xong" and u.get("tran")):
            cu = getattr(client, "_qct_khong_tien", None)
            client._qct_khong_tien = (sig, cu[1] + 1 if cu and cu[0] == sig else 1,
                                      "item_khong_co" if kq == "xong" else kq)
        return du
    if u.get("mo"):
        return _dao_mo(client, u, abort, log)
    diem = (int(u["scene"]), int(u["x"]), int(u["y"]))
    if getattr(client, "_qct_farm", None) != diem:
        client._qct_farm = diem
        client._qct_farm_t = time.time()
        try:
            client.combat_ready()        # bat lai hop may o diem quai (y train) -> quai tu vao tran
        except Exception:
            pass
        if log is not None:
            log.info("[%s] QUEST CT: danh quai lay item %s x%s quanh map %s (%s,%s) - khong gioi "
                     "han tran, %s (tui co %s)", label, u["item"], u["count"], u["scene"], u["x"],
                     u["y"], "DI LAI quanh diem (khong co quai lao vao)" if u.get("di_lai")
                     else "dung yen cho quai lao vao", _so_item(client, u["item"]))
    han = time.time() + 60.0
    vong = _diem_quanh(u["x"], u["y"]) if u.get("di_lai") else None
    i = 0
    while time.time() < han and client.running and not (abort is not None and abort()):
        if _so_item(client, u["item"]) >= int(u["count"]):
            break
        if vong:
            # Map chi co tran ngau nhien KHI DI (11176 map 12582: dung yen 21 phut 0 tran)
            client.flee_mode = False
            client.navigate_to(*vong[i % len(vong)], abort=abort, flee=False)
            i += 1
            continue
        time.sleep(1.0)
    du = _so_item(client, u["item"]) >= int(u["count"])
    if du:
        client._qct_farm = None
        if log is not None:
            log.info("[%s] QUEST CT: DU item %s (%s/%s) sau %ds danh quai", label, u["item"],
                     _so_item(client, u["item"]), u["count"],
                     int(time.time() - getattr(client, "_qct_farm_t", time.time())))
    return du


def _dao_mo(client, u, abort, log):
    """Danh quai trong VUNG MO (map mo khong co tran ngau nhien): deo Cuoc neu quai khoang, di lai
    trong vung cho server kich hoat tran, KHONG bo chay quai khoang. ~60s moi nhip."""
    label = getattr(client, "_label", "?")
    mo = u["mo"]
    khoang = _mo_khoang(u)
    if khoang and not _deo_cuoc(client, log):
        if log is not None:
            log.warning("[%s] QUEST CT: chua deo duoc Cuoc -> chua vao mo", label)
        return False
    diem = (int(u["scene"]), int(mo["id"]))
    if getattr(client, "_qct_farm", None) != diem:
        client._qct_farm = diem
        client._qct_farm_t = time.time()
        if log is not None:
            log.info("[%s] QUEST CT: dao mo %s map %s (x %s-%s, y %s-%s, quai lv%s %s) lay item %s "
                     "x%s - di lai trong vung mo, %s (tui co %s)", label, mo["id"], u["scene"],
                     mo["x0"], mo["x1"], mo["y0"], mo["y1"], mo.get("lv"), mo.get("quai"),
                     u["item"], u["count"], "DEO CUOC, KHONG bo chay quai khoang" if khoang
                     else "danh quai gap phai", _so_item(client, u["item"]))
    han = time.time() + 60.0
    for x, y in _diem_mo(mo) * 4:
        if (time.time() >= han or not client.running or (abort is not None and abort())
                or _so_item(client, u["item"]) >= int(u["count"])):
            break
        st = getattr(client, "state", None)
        if st is not None and khoang:
            st.danh_khoang_den = time.time() + _DANH_KHOANG_GIAY
        client.flee_mode = False
        client.navigate_to(int(x), int(y), abort=abort, flee=False)
    du = _so_item(client, u["item"]) >= int(u["count"])
    if du:
        client._qct_farm = None
        if log is not None:
            log.info("[%s] QUEST CT: DU item %s (%s/%s) sau %ds dao mo", label, u["item"],
                     _so_item(client, u["item"]), u["count"],
                     int(time.time() - getattr(client, "_qct_farm_t", time.time())))
        if getattr(client, "_qct_vk_cu", None):
            _thao_cuoc(client, log)
    return du


def _cat_nha_tro(client, sig, t, abort, log):
    """Gui NPC `t["npc"]` dang di theo vao NHA TRO (12290 B7 "hãy gửi Cửu Sởi vào Nhà Trọ"): toi chu
    nha tro, chon "Võ Tướng" (server mo bang S:031-007) -> C:031-003 o di theo. True = xong / khong
    can (NPC khong di theo)."""
    label = getattr(client, "_label", "?")
    o = sorted(int(k) for k, v in (getattr(client, "follow_npc", None) or {}).items()
               if int(v) == int(t["npc"]))
    if not o:
        if log is not None:
            o_tro = int(t["npc"]) in {int(v) for v in (getattr(client, "vantieu_roster_ids", None)
                                                       or {}).values()}
            log.info("[%s] QUEST CT: NPC %s khong di theo (%s) -> lam buoc luon", label, t["npc"],
                     "DA O nha tro" if o_tro else "nha tro cung khong thay")
        return True
    if not _di_toi(client, t["scene"], t["x"], t["y"], abort):
        return False
    client.flee_mode = False
    client.quest_kich_hoat(t["kieu"], int(t["idx"]))
    kq = client.quest_hoi_thoai(chon=dict(t.get("chon_map") or {}), abort=abort, im_lang=20.0,
                                nha_tro=o[0])
    han = time.time() + 3.0
    while _dang_theo(client, t["npc"]) and time.time() < han and client.running:
        time.sleep(0.2)              # S:015-002 xoa o di theo co the toi sau
    con = bool(_dang_theo(client, t["npc"]))
    if log is not None:
        (log.warning if con else log.info)(
            "[%s] QUEST CT: gui NPC %s (o %s) vao nha tro (map %s %s %s) -> su kien %s, %s", label,
            t["npc"], o[0], t["scene"], t["kieu"], t["idx"], kq,
            "VAN DI THEO - chua gui duoc" if con else "DA GUI")
    if con and kq != "dung":
        cu = getattr(client, "_qct_khong_tien", None)
        client._qct_khong_tien = (sig, cu[1] + 1 if cu and cu[0] == sig else 1, "nha_tro")
    return not con


def lam_buoc_ct(client, q, b, d, abort=None, log=None):
    """Lam MOT buoc quest chinh tuyen, DI LE. True = len buoc / xong / chuyen tiep."""
    label = getattr(client, "_label", "?")
    if getattr(client, "party_members", None) or getattr(client, "party_leader", None):
        # Thanh vien party tu di theo doi truong, KHONG tu di chuyen duoc (KNOWLEDGE 7d) -> roi doi.
        if log is not None:
            log.info("[%s] QUEST CT: dang trong party -> roi doi de di le", label)
        client.leave_party()
        time.sleep(1.0)
    if not client._wait_combat_clear(idle=1.0, cap=120.0):
        return False
    if log is not None:
        log.info("[%s] QUEST CT: %s", label, _mo_ta(q, b, d))
    sig = (int(q["id"]), b)
    if getattr(client, "_qct_vk_cu", None) and not any(u.get("mo") for u in _can_item(client, d)):
        _thao_cuoc(client, log)
    for u in _can_item(client, d):
        if not _lay_item(client, sig, u, abort, log):
            return False
    for l in _can_lay(client, d):
        # Buoc can DAN NPC ma NPC chua theo -> di lay truoc (10023 B1: noi chuyen ngua NPC 9 map
        # 12001, surface 11 chon 30 "Bat ve cho han xem thu vay" -> xin gia nhap). User 09/10:
        # "chi can chay di noi chuyen voi con ngua la se co ngua".
        if not _di_toi(client, l["scene"], l["x"], l["y"], abort):
            return False
        client.flee_mode = False
        client.quest_kich_hoat(l["kieu"], int(l["idx"]))
        kq = client.quest_hoi_thoai(chon=dict(l.get("chon_map") or {}), abort=abort)
        han = time.time() + 3.0
        while not _dang_theo(client, l["npc"]) and time.time() < han and client.running:
            time.sleep(0.2)          # S:015-001 co the toi sau khi hoi thoai dong
        theo = bool(_dang_theo(client, l["npc"]))
        if log is not None:
            (log.info if theo else log.warning)(
                "[%s] QUEST CT: lay NPC %s (map %s %s %s) -> su kien %s, %s", label, l["npc"],
                l["scene"], l["kieu"], l["idx"], kq,
                "DA DI THEO" if theo else "KHONG DI THEO (vo tuong %s)" % (
                    getattr(client, "follow_npc", None),))
        if not theo:
            if kq != "dung":
                cu = getattr(client, "_qct_khong_tien", None)
                client._qct_khong_tien = (sig, cu[1] + 1 if cu and cu[0] == sig else 1,
                                          "npc_khong_theo" if kq == "xong" else kq)
            return False
    for t in d.get("cat_tro") or ():
        if not _cat_nha_tro(client, sig, t, abort, log):
            return False
    if not _di_toi(client, d["scene"], d["x"], d["y"], abort):
        if log is not None:
            log.warning("[%s] QUEST CT: chua toi duoc map %s (%s,%s), dang o %s", label, d["scene"],
                        d["x"], d["y"], getattr(client, "current_map", None))
        return False
    chon = dict(d.get("chon_map") or {})
    for t in d.get("truoc") or ():
        # Cua su kien phai cham truoc (10528 B2: cua 3 -> hien NPC 1)
        if not _di_toi(client, d["scene"], t["x"], t["y"], abort):
            return False
        client.flee_mode = False
        client.quest_kich_hoat("cua", int(t["cua"]))
        kq = client.quest_hoi_thoai(chon=chon, abort=abort, im_lang=15.0)
        if log is not None:
            log.info("[%s] QUEST CT: cham cua %s truoc -> %s", label, t["cua"], kq)
        if kq != "xong" or not _di_toi(client, d["scene"], d["x"], d["y"], abort):
            return False
    qid = int(q["id"])
    truoc = dict(getattr(client, "mission_steps", None) or {})
    # flee_mode chi tac dung khi KHONG o party (client.py `flee_mode and not party_members`): di le
    # ma de bat thi gap boss quest bot BO CHAY -> khong bao gio len buoc.
    client.flee_mode = False
    client.quest_kich_hoat(d["kieu"], int(d["idx"]))
    kq = client.quest_hoi_thoai(chon=chon, abort=abort)
    sau = dict(getattr(client, "mission_steps", None) or {})
    xong = bool(client.mark_flag_get(int(q["bit"])))
    # Tien = co xong / buoc doi / server giao mission moi (Gian Ung: xoa 12288 + giao 10001)
    tien = xong or int(sau.get(qid, 0)) != int(truoc.get(qid, 0)) or bool(set(sau) - set(truoc))
    ok = kq == "xong" and tien
    if ok:
        client._qct_khong_tien = None
    elif kq != "dung":
        # Dem MOI ket qua khong len buoc tru "dung" (bi huy tu ngoai): truoc chi dem "xong" ->
        # `im_lang` (server khong phan hoi) thu mai, moi lan mat 60s (log p52 09/10 vuchin/vummot).
        cu = getattr(client, "_qct_khong_tien", None)
        client._qct_khong_tien = (sig, cu[1] + 1 if cu and cu[0] == sig else 1, kq)
    if xong:
        da = getattr(client, "_qct_da_xong", None)
        if da is None:
            da = client._qct_da_xong = set()
        da.add(qid)
        try:
            client.claim_achievements()     # thuong thanh tuu "xong quest X" (kind 15)
        except Exception as e:
            if log is not None:
                log.warning("[%s] QUEST CT: loi nhan thuong thanh tuu: %s", label, e)
    if log is not None:
        (log.info if ok else log.warning)(
            "[%s] QUEST CT: %s buoc %s -> su kien %s, buoc %s -> %s%s", label, q["name"], b, kq,
            truoc.get(qid, 0), sau.get(qid, 0),
            " (XONG QUEST - %d quest trong phien)" % len(client._qct_da_xong)
            if xong else ("" if ok else " -> KHONG LEN BUOC"))
    return ok


def chay_chinh_tuyen(client, key, abort=None, log=None, cho=30.0):
    """NAC B: moi nhip lam MOT buoc cua quest [Chinh] dau tien LAM DUOC trong so nhiem vu (cach a).

    Quest/buoc chua lam duoc -> `client._qct_chu_y` (len "Chu y"), xet quest sau ([Chinh] roi
    [Huong Dan]). So khong con quest [Chinh]/[Huong Dan] nao -> `client._qct_het` = True (engine tat
    game acc - user 08/10 "dung va tat game"). KHONG gioi han so quest moi phien (user 09/10).
    """
    kh = ke_hoach_chinh_tuyen(client, key)
    if kh is None:
        _ngu(2.0, abort)
        return True
    _log_ke_hoach(client, kh, log, "LAM THAT")
    da = getattr(client, "_qct_da_xong", None) or set()
    ket, lam = [], None
    for q, b, d in kh["se_lam"]:
        ly = ly_do_ket(client, key, q, b, d)
        if ly:
            ket.append({"id": int(q["id"]), "ten": q["name"], "buoc": "%s/%s" % (
                b, len(q["steps"])), "ly_do": ly})
        else:
            lam = (q, b, d)
            break
    client._qct_chu_y = ket
    if lam is not None:
        if not lam_buoc_ct(client, *lam, abort=abort, log=log):
            _ngu(5.0, abort)       # khong lam nong: lan sau tu tinh lai tu trang thai server
        return True
    label = getattr(client, "_label", "?")
    if not ket:
        if not getattr(client, "_qct_het", False) and log is not None:
            log.info("[%s] QUEST CT: HET quest lam duoc (xong %d quest trong phien, so con %d quest "
                     "[Chinh]/[Huong Dan]) -> TAT GAME", label, len(da), len(kh["se_lam"]))
        client._qct_het = True
    elif log is not None and getattr(client, "_qct_ket_log", None) != ket:
        client._qct_ket_log = ket
        for k in ket:
            log.warning("[%s] QUEST CT: DUNG YEN - %s buoc %s: %s", label, k["ten"], k["buoc"],
                        k["ly_do"])
    _ngu(cho, abort)
    return True
