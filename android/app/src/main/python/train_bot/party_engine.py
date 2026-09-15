"""ENGINE PARTY MOI - MOT luong quyet dinh cho ca party (thiet ke: documents/ENGINE_PARTY_MOI.md).

VI SAO CO FILE NAY
------------------
Engine cu cho moi acc mot thread chay kich ban rieng (`run_account`, 5.690 dong). Do trong chinh
ham do: 39 vong CHO, 21 vong KHONG CO HAN, va **14 vong diec voi `reform_gen`**. Moi vong cho phai
TU NHO nghe 4 loai lenh (kenh / reform / rally / cmd) => 84 o phai nho, lap duoc ~11. Moi lan user
bao loi la MOT O TRONG.

Ca de ra file nay - party 11, 15/09 (`luumuoi` treo 64 phut, party ket 22 phut):
    11:25:22 [luumuoi] (member) ca party xong dungeon      <- IM TUYET DOI tu day, 0 dong/64 phut
    12:27:51 [luusau]  (LEADER) -> REFORM party (gen 30)   <- leader lam dung, lan thu 8 lien tiep
    12:27:51 [luusau]  reform: dieu phoi bao GOM -> thoi moi
`do_daily_dungeon()` phai `leave_party()` (PB don bat buoc solo) -> party vo -> `luumuoi` roi vao
vong `while not st["invited"].is_set()`, vong do nghe lenh KENH va `rally_gen` nhung KHONG nghe
`reform_gen` - ma lenh gom map lai di bang `reform_gen`. Ba ben deu "dung luat" nen ket vinh vien.

GOC KHONG PHAI "moi acc mot thread". Goc la: **moi acc tu quyet dinh luc nao thi nghe lenh.**

CACH CHUA
---------
Luong quyet dinh KHONG CO VONG CHO NAO. Moi nhip: doc anh chup trang thai 5 client -> `quyet_dinh()`
(ham THUAN, khong I/O, khong sleep) -> giao viec cho worker. Vi khong chan, moi lenh deu duoc xu ly
o nhip ke tiep - tre toi da mot nhip. Khong ton tai khai niem "vong cho diec".

Viec CHAN (di duong, vao Di Gioi, danh pho ban) chay o worker rieng tung acc va HUY duoc giua chung
=> giu duoc cach ly loi cua engine cu: mot acc treo khong lam dung ca party.

KHONG NOI LUAT NAO trong documents/RULE_DIEU_PHOI.md. Dieu phoi quyet, acc thi hanh (L1); du party
roi lam gi thi lam, party hong thi gom bang duoc (L0).
"""
from __future__ import annotations

import threading
import time

# ---------------------------------------------------------------- viec (lenh cho worker)

VIEC_NGHI = "nghi"                # khong co viec - dung yen
VIEC_VE_MAP = "ve_map"            # di ve map chung (dong bo map)
VIEC_DOI_KENH = "doi_kenh"        # chuyen sang kenh chung
VIEC_LAP_PARTY = "lap_party"      # leader moi, member cho nhan
VIEC_TRAIN = "train"              # du doi, cung cho -> danh
VIEC_VIEC_VAT = "viec_vat"        # PB don / boss the gioi / daily - acc nam han trong client
VIEC_LOGIN_CHORE = "login_chore"  # viec vat sau login (PB don, boss TG, nhiem vu ngay, van tieu)
VIEC_DI_GIOI = "di_gioi"          # vao Di Gioi (mode digioi / digioi_train pha DG)
VIEC_RA_SPOT = "ra_spot"          # du party, dung map -> keo ra bai quai
VIEC_PB_DOI = "pb_doi"            # LEADER chay pho ban to doi (lv20/50/80/110)
VIEC_PB_DOI_THEO = "pb_doi_theo"  # member: mo cua nhan loi moi + DUNG YEN cho leader keo vao

# Thu tu uu tien, dung y chuoi user chot tu dau:
#   "lech map thi dong bo map / lech kenh thi dong bo kenh / cung kenh cung map thi lap pt /
#    du pt thi chay di train"
THU_TU = (VIEC_LOGIN_CHORE, VIEC_DI_GIOI, VIEC_VE_MAP, VIEC_DOI_KENH, VIEC_LAP_PARTY,
          VIEC_PB_DOI, VIEC_PB_DOI_THEO, VIEC_RA_SPOT, VIEC_TRAIN, VIEC_VIEC_VAT, VIEC_NGHI)

# PHA cua party mode `digioi_train` (giong `st["dt_phase"]` cua engine cu)
PHA_DG = "digioi"        # con gio Di Gioi -> ca party vao DG danh
PHA_TRAIN = "train"      # het gio DG -> ra map thuong gom party + train


class AnhAcc:
    """ANH CHUP trang thai mot acc tai MOT khoanh khac.

    Vi sao phai chup thay vi doc thang `client` trong luc quyet dinh: engine cu doc map/kenh cua
    tung acc o nhung thoi diem KHAC NHAU nen sinh ra ba thuc tai lech nhau (ca party 11: leader
    "biet" minh o thanh gom, member "biet" minh o bai train, dieu phoi thay 2 map). Chup mot lan
    roi quyet dinh tren anh do => ca party dung chung MOT su that.
    """

    __slots__ = ("username", "la_leader", "song", "map_id", "kenh", "dang_danh",
                 "so_member", "viec_vat", "viec_dang_lam", "xong_chore", "trong_dg",
                 "con_gio_dg")

    def __init__(self, username, la_leader=False, song=True, map_id=None, kenh=None,
                 dang_danh=False, so_member=0, viec_vat=False, viec_dang_lam=VIEC_NGHI,
                 xong_chore=True, trong_dg=False, con_gio_dg=False):
        self.username = username
        self.la_leader = bool(la_leader)
        self.song = bool(song)
        self.map_id = map_id
        self.kenh = kenh
        self.dang_danh = bool(dang_danh)
        self.so_member = int(so_member or 0)
        self.viec_vat = bool(viec_vat)          # dang PB don / boss the gioi / daily
        self.viec_dang_lam = viec_dang_lam
        self.xong_chore = bool(xong_chore)      # da lam xong viec vat sau login chua
        self.trong_dg = bool(trong_dg)          # dang o trong map Di Gioi
        self.con_gio_dg = bool(con_gio_dg)      # server bao con phut Di Gioi hom nay

    def __repr__(self):
        return "<%s map=%s k=%s%s%s>" % (self.username, self.map_id, self.kenh,
                                         " danh" if self.dang_danh else "",
                                         " vat" if self.viec_vat else "")


class AnhParty:
    """Anh chup ca party + dich ma engine dang nham toi."""

    __slots__ = ("pidx", "accs", "can_bao_nhieu", "map_dich", "luc", "pha", "co_spot",
                 "pb_doi_level")

    def __init__(self, pidx, accs, can_bao_nhieu=0, map_dich=None, luc=None,
                 pha=PHA_TRAIN, co_spot=False, pb_doi_level=None):
        self.pidx = int(pidx)
        self.accs = list(accs)
        self.can_bao_nhieu = int(can_bao_nhieu or 0)   # so member can (khong ke leader)
        self.map_dich = map_dich                       # map train / diem tap ket da chot
        self.luc = float(luc if luc is not None else time.time())
        self.pha = pha                                 # PHA_DG / PHA_TRAIN
        self.co_spot = bool(co_spot)                   # da chot duoc tam bai quai chua
        self.pb_doi_level = pb_doi_level               # level PB to doi con luot (None = het)

    # --- doc tinh hinh: CHI tinh acc dang song va KHONG lam viec vat ---
    #
    # Acc dang viec vat PHAI o map khac (ban Noi Dan o Nghiep Thanh, cat tien trang, boss the gioi
    # - user 14/09), nen dem no vao phep do la party LUC NAO cung "lech map". Lenh van chay binh
    # thuong tren so acc con lai; acc kia giu loi moi, xong viec thi nhan.
    def _dem_duoc(self):
        return [a for a in self.accs if a.song and not a.viec_vat]

    def maps(self):
        return sorted({a.map_id for a in self._dem_duoc() if a.map_id is not None})

    def kenhs(self):
        return sorted({a.kenh for a in self._dem_duoc() if a.kenh})

    def leader(self):
        for a in self.accs:
            if a.la_leader and a.song:
                return a
        return None

    def roster_leader(self):
        """So member LEADER dang thay. Doc cua LEADER chu khong phai ban sao ngheo nhat: moi acc
        giu mot ban roster rieng, ban cua member thuong cu hon (party 11 - leader thay 3/4 trong khi
        co member con thay 1/4) va lay ban ngheo nhat thi engine tuong party hong, gom lai vo ich."""
        lead = self.leader()
        return lead.so_member if lead is not None else 0


# ---------------------------------------------------------------- nhip quyet dinh (HAM THUAN)

def _map_dich(anh: AnhParty, con_lai, maps):
    """Party dang o nhieu map -> DON VE DAU khi engine chua chot diem tap ket.

    Ve map DONG NGUOI NHAT, hoa thi theo LEADER. Lay bua mot map (vd map nho nhat) la co luc bat ba
    dua dang dung dung cho di theo mot dua lac - chinh la kieu "gom" tra gia dat nhat: ca party roi
    bai train de chay theo nguoi chet hoi sinh o thanh.
    """
    if not maps:
        return None
    dem = {}
    for a in con_lai:
        if a.map_id is not None:
            dem[a.map_id] = dem.get(a.map_id, 0) + 1
    if not dem:
        return None
    dong_nhat = max(dem.values())
    ung_vien = [m for m, n in dem.items() if n == dong_nhat]
    if len(ung_vien) > 1:
        lead = anh.leader()
        if lead is not None and lead.map_id in ung_vien:
            return lead.map_id
    return sorted(ung_vien)[0]


def quyet_dinh(anh: AnhParty):
    """(anh chup) -> {username: viec}. HAM THUAN: khong I/O, khong sleep, khong doc dong ho.

    Test duoc thang, va vi khong chan nen KHONG THE co "vong cho diec" - do la ca diem cua engine
    nay. Do tren engine cu: mot quyet dinh danh = 0,014ms (p99 0,024ms), 5 acc = 0,1ms tren ngan
    sach `submit_delay` 500ms => nhip 1 giay du cho ca tram party.
    """
    song = [a for a in anh.accs if a.song]
    if not song:
        return {}

    ket = {}
    # (0a) Acc dang viec vat: KHONG QUAY RAY (user 14/09 - "khi dang danh PB don va daily quest thi
    # dieu phoi tam thoi ko quay ray"). Xong viec no tu quay lai hang doi o nhip sau.
    for a in song:
        if a.viec_vat:
            ket[a.username] = VIEC_VIEC_VAT

    # (0b) CHUA XONG VIEC VAT SAU LOGIN -> lam cho xong, dung keo di dau.
    #
    # User 14/09: "dang lam may cai viec vat do ko vao pt la dung... vao pt roi bi keo di luon thi
    # no hong viec vat". Va cua hoan cu (bo 14/09) tung lam 96% acc mat luot PB don CA NGAY vi
    # dieu phoi luc nao cung dang gom dung luc acc moi login.
    for a in song:
        if a.username not in ket and not a.xong_chore:
            ket[a.username] = VIEC_LOGIN_CHORE

    con_lai = [a for a in song if a.username not in ket]
    if not con_lai:
        return ket

    # (0c) PHA DI GIOI: con gio thi CA PARTY vao DG. Di Gioi la instance rieng - vao roi thi khong
    # con khai niem lech map/kenh voi nhau, nen cat truoc ca chuoi gom.
    if anh.pha == PHA_DG:
        for a in con_lai:
            if a.trong_dg:
                ket[a.username] = VIEC_TRAIN          # trong DG roi -> danh
            elif a.con_gio_dg:
                ket[a.username] = VIEC_DI_GIOI
            else:
                ket[a.username] = VIEC_NGHI           # het gio - cho ca party doi pha
        return ket

    # (0d) PHO BAN TO DOI - dat TRUOC ca chuoi gom map/kenh/lap party.
    #
    # DUONG LAP DOI CUA PB KHAC HAN party thuong (user 15/09: "duong lap pt PB no khac voi lap pt
    # di train"). Theo KNOWLEDGE.md:
    #   - party thuong: moi `0x0d/0900`, member phai mo gate (`set_party_invite_ready`)
    #   - phong PB    : moi `Dungeon.SendInvite` -> `0x2f/0800`; member nhan `0x2f/0f00` roi
    #                   join room `0x2f/0300` + ready `0x2f/0b00` - `_on_dungeon` TU LAM het,
    #                   member khong phai lam gi ca
    # "PB invite KHONG bat buoc check gan nhu party thuong vi server/client cho moi theo roleId da
    # biet" => KHONG can cung map, KHONG can cung kenh, KHONG can du party thuong truoc.
    # Bat party gom du 4/4 roi moi cho danh PB la tu dat them dieu kien ma game khong doi, va moi
    # phut gom la mot phut co the mat luot PB.
    if anh.pb_doi_level is not None:
        for a in con_lai:
            ket[a.username] = VIEC_PB_DOI if a.la_leader else VIEC_PB_DOI_THEO
        return ket

    maps = anh.maps()
    # (1) LECH MAP -> dong bo map. Chua biet map cua ai do (None) cung phai cho, khong ket luan.
    if len(maps) > 1 or any(a.map_id is None for a in con_lai):
        dich = anh.map_dich if anh.map_dich in maps else _map_dich(anh, con_lai, maps)
        for a in con_lai:
            ket[a.username] = VIEC_NGHI if a.map_id == dich and dich is not None else VIEC_VE_MAP
        return ket

    # (2) CUNG MAP roi -> moi xet KENH (user chot: "dong bo map xong moi xem den kenh").
    kenhs = anh.kenhs()
    if len(kenhs) > 1:
        dich = kenhs[0]
        for a in con_lai:
            ket[a.username] = VIEC_NGHI if a.kenh == dich else VIEC_DOI_KENH
        return ket

    # (3) Cung map + cung kenh -> LAP PARTY neu chua du.
    if anh.can_bao_nhieu > 0 and anh.roster_leader() < anh.can_bao_nhieu:
        for a in con_lai:
            ket[a.username] = VIEC_LAP_PARTY
        return ket

    # (4) Du doi, cung map cung kenh -> RA BAI QUAI roi moi danh.
    #
    # Ca that 14/09 (user: "vay la dang o thanh, thay vi chay ra map train may lai tinh la dang o
    # map train va chay ra spot a"): "du party" KHONG co nghia la "dung yen danh o bat cu dau".
    # Chua co tam bai quai thi dung yen cho leader chot, dung bat combat giua thanh.
    if not anh.co_spot:
        for a in con_lai:
            ket[a.username] = VIEC_NGHI
        return ket
    for a in con_lai:
        ket[a.username] = VIEC_TRAIN if a.viec_dang_lam == VIEC_TRAIN else VIEC_RA_SPOT
    return ket


# ---------------------------------------------------------------- worker (thi hanh viec CHAN)

class AccWorker:
    """MOT thread moi acc, chi lam MOT viec tai mot thoi diem, va HUY duoc giua chung.

    Vi sao van can thread rieng thay vi "mot thread lam tat": mot acc mat goi se lam dung ca nhip
    cua party, va mot exception giet luon 5 acc. Tach ra thi giu duoc cach ly loi cua engine cu
    (ca that 15/09: `luumuoi` treo nhung `luusau` van reform deu 8 lan).

    Viec = goi THANG ham co san trong `GameClient` (`do_daily_dungeon`, `enter_di_gioi_safe`,
    `navigate_to`, `switch_channel`...). KHONG viet lai thao tac game - 3030 test dang phu chung.
    """

    def __init__(self, username, client, lam_viec):
        self.username = username
        self.client = client
        self._lam_viec = lam_viec          # (client, viec, huy_fn) -> None
        self._viec = VIEC_NGHI
        self._viec_moi = None
        self._huy = threading.Event()
        self._lock = threading.Lock()
        self._th = None
        self._dung = threading.Event()
        self.loi_cuoi = None

    # -- engine goi --
    def giao(self, viec):
        """Giao viec MOI. Viec cu (neu khac) bi HUY - khong xep hang, vi lenh moi luon dung hon."""
        with self._lock:
            if viec == self._viec and self._viec_moi is None:
                return False
            self._viec_moi = viec
            self._huy.set()        # bao viec dang chay dung lai
            return True

    def viec_hien_tai(self):
        with self._lock:
            return self._viec

    def start(self):
        if self._th is not None and self._th.is_alive():
            return
        self._dung.clear()
        self._th = threading.Thread(target=self._vong, name="worker-%s" % self.username,
                                    daemon=True)
        self._th.start()

    def stop(self):
        self._dung.set()
        self._huy.set()

    # -- than worker --
    def _vong(self):
        while not self._dung.is_set():
            with self._lock:
                moi, self._viec_moi = self._viec_moi, None
                if moi is not None:
                    self._viec = moi
                viec = self._viec
            self._huy.clear()
            if viec in (None, VIEC_NGHI):
                time.sleep(0.2)
                continue
            try:
                self._lam_viec(self.client, viec, self._con_lam)
            except Exception as e:      # mot viec loi KHONG duoc giet worker: nhip sau giao lai
                self.loi_cuoi = e
                time.sleep(0.5)

    def _con_lam(self):
        """Truyen xuong thao tac chan lam `abort=`: co lenh moi / bi dung -> nha ra ngay.
        `client.py` da co san duong nay (`navigate_to(..., abort=...)`)."""
        return not (self._huy.is_set() or self._dung.is_set())


# ---------------------------------------------------------------- anh xa viec -> ham THAT
#
# KHONG viet lai thao tac game: moi viec goi thang ham co san trong `GameClient`, thu da chay that
# hang thang va duoc 3030 test phu. Engine moi chi doi CACH RA LENH, khong doi cach lam.

def thi_hanh(client, viec, con_lam, dich=None, log=None):
    """Lam mot viec. `con_lam()` False = co lenh moi -> NHA RA ngay (khong lam not).

    `abort=` la duong huy da co san trong `client.py`; day la ly do engine moi khong can vong cho:
    lenh moi khong phai "doi acc nghe thay", ma la CAT NGANG viec dang lam.
    """
    _abort = lambda: not con_lam()
    if viec == VIEC_VE_MAP:
        if dich is None or int(getattr(client, "current_map", 0) or 0) == int(dich):
            return True
        return bool(client.follow_smart_route(int(dich), None, abort=_abort, flee=True))
    if viec == VIEC_DOI_KENH:
        if dich is None or int(getattr(client, "current_channel", 0) or 0) == int(dich):
            return True
        return bool(client.switch_channel(int(dich)))
    if viec == VIEC_LAP_PARTY:
        # Leader moi, member mo cua nhan. Member KHONG tu moi ai (L1) va cung khong tu roi doi.
        if getattr(client, "_pe_la_leader", False):
            return bool(client.invite_train_party_participants(gap=1.0))
        client.set_party_invite_ready(True)
        return True
    if viec == VIEC_DI_GIOI:
        # `enter_di_gioi_safe` da tu doc `S:097-001` va gian ra khi server im (sua 15/09) - khong
        # duoc ban lai o day, ban day chinh la thu da lam 264 acc-lan `VAO DI GIOI THAT BAI`.
        return bool(client.enter_di_gioi_safe())
    if viec == VIEC_LOGIN_CHORE:
        return lam_viec_vat(client, log=log, con_lam=con_lam)
    if viec == VIEC_PB_DOI:
        # LEADER chay kich ban PB to doi co san (`do_team_dungeon_lv20/50/80/110`). Chan 10-20
        # phut la BINH THUONG - 5 tran + di duong + thoai. KHONG dat han cho o day: engine cu tung
        # co watchdog 180s va no da keo CA 4 MEMBER ra relogin GIUA pho ban, pha nat luot PB.
        if dich is None:
            return True
        return bool(client.do_team_dungeon(int(dich)))
    if viec == VIEC_PB_DOI_THEO:
        # Member KHONG dung toi cua party THUONG o day: loi moi phong PB di duong rieng
        # (`0x2f/0f00`) va `_on_dungeon` da TU accept + ready khi `auto_accept_party` bat.
        # Goi `set_party_invite_ready(True)` o day la mo nham cua - vua khong giup gi cho PB, vua
        # cho loi moi party thuong lot vao giua luc dang cho phong PB.
        client.auto_accept_party = True
        client.flee_mode = True      # dung danh le trong luc cho leader keo vao phong
        return True
    if viec == VIEC_RA_SPOT:
        if dich is None:
            return False
        client.flee_mode = False      # du party -> keo ra spot phai DANH bat chap, khong flee
        return bool(client.navigate_to(int(dich[0]), int(dich[1]), flee=False, abort=_abort))
    if viec == VIEC_TRAIN:
        client.flee_mode = False
        try:
            client.combat_ready()
        except Exception:
            pass
        return True
    if viec == VIEC_VIEC_VAT:
        # Acc dang nam han trong `client` (PB don / boss the gioi) - KHONG quay ray (user 14/09).
        return True
    return True


# ---------------------------------------------------------------- viec vat sau login
#
# KHONG viet lai mot viec nao: goi thang ham co san trong `GameClient`. Thu tu theo dung engine cu.
# Moi viec boc rieng: mot viec loi KHONG duoc lam mat nhung viec con lai (truoc day ca chuoi nam
# trong mot try -> hong mot cai la mat sach).
# (co trong pcfg, ten ham trong GameClient). Ten ham da doi chieu voi bot/client.py - dat sai ten
# thi `getattr` tra None va viec do bi BO QUA AM THAM, dung kieu loi `_load_gamedata_items()` da
# can hai lan trong mot ngay (xem CLAUDE.md).
CHORE = (
    ("claim_offline_exp", "request_offline_exp"),
    ("auto_discard_junk", "discard_junk_items"),
    ("auto_decompose_scrolls", "decompose_junk_scrolls"),
    ("auto_sell_noi_dat", "sell_noi_dat"),
    ("do_daily", "do_daily_dungeon"),
    ("auto_world_boss", "do_world_boss_all"),
    ("fight_legion_boss", "do_legion_boss"),
    ("do_van_tieu", "do_van_tieu"),
    ("do_daily", "claim_daily_quests"),
)


def lam_viec_vat(client, pcfg=None, log=None, con_lam=None):
    """Lam viec vat sau login. Tra True khi da chay het (du co viec loi).

    Danh dau `_pe_xong_chore = True` khi xong: nhip sau doc co do de thoi giao viec nay. Khong
    dung dong ho - acc cham may cung phai lam xong, khong ai duoc dat han cho no (user 14/09:
    "m dat han 300s, sau 300 ma no van chua xong viec vat thi sao").
    """
    pcfg = pcfg if pcfg is not None else getattr(client, "_pe_pcfg", {}) or {}
    for co, ten_ham in CHORE:
        if con_lam is not None and not con_lam():
            return False                     # co lenh moi -> nha ra, nhip sau lam tiep
        if co and not pcfg.get(co, True):
            continue
        ham = getattr(client, ten_ham, None)
        if ham is None:
            continue
        try:
            ham()
        except Exception as e:
            if log is not None:
                log.warning("[%s] ENGINE: viec vat '%s' loi (bo qua): %s",
                            getattr(client, "_label", "?"), ten_ham, e)
    client._pe_xong_chore = True
    return True


def _goi(client, ten, mac_dinh=None):
    """Goi mot ham cua client, loi/thieu -> tra mac dinh.

    Doc TUNG TRUONG doc lap chu khong boc ca anh trong mot try: thieu MOT API (vd client cu chua
    co `digioi_minutes_live`) ma lam ca acc bi coi la CHET thi engine se tuong party hong va gom
    lai vo tan - dat hon nhieu so voi viec chi mat mot truong.
    """
    ham = getattr(client, ten, None)
    if ham is None:
        return mac_dinh
    try:
        return ham()
    except Exception:
        return mac_dinh


# ---------------------------------------------------------------- PartyEngine (1 thread / party)

NHIP_SEC = 1.0


class PartyEngine:
    """MOT thread quyet dinh cho ca party. Khong chan o bat ky dau trong nhip.

    Vong doi mot nhip:
        chup anh 5 client  ->  quyet_dinh(anh)  ->  giao viec cho worker  ->  return
    Khong `while` cho ai, khong `sleep` giua chung. Vi the moi lenh (ke ca lenh do CHINH no vua
    ra o nhip truoc) deu duoc xet lai o nhip sau - tre toi da NHIP_SEC.

    So sanh voi engine cu: `run_account` co 21 vong cho khong han, 14 vong diec voi `reform_gen`.
    O day con so do la 0, va `tests/test_party_engine_nhip.py` chan bang AST khong cho mọc lai.
    """

    def __init__(self, pidx, doc_clients, can_bao_nhieu=0, map_dich=None, log=None,
                 bao_gui=None, pha=PHA_TRAIN, gio_dg_toi_da=120, doc_spot=None,
                 pb_doi_levels=(), ghi_pha=None):
        self.pidx = int(pidx)
        self._doc_clients = doc_clients      # () -> [(username, client, la_leader)]
        self.can_bao_nhieu = int(can_bao_nhieu or 0)
        self.map_dich = map_dich
        self._log = log
        self._bao_gui = bao_gui          # (username, mo_ta, pha) -> None : cho GUI thay
        self.pha = pha                   # PHA_DG / PHA_TRAIN (mode digioi_train doi pha giua chung)
        self.gio_dg_toi_da = int(gio_dg_toi_da or 120)
        self._doc_spot = doc_spot        # () -> (x, y) | None : tam bai quai leader da chot
        self.pb_doi_levels = tuple(pb_doi_levels or ())   # level PB to doi user BAT trong config
        self._ghi_pha = ghi_pha          # (pha) -> None : ghi nguoc `dt_phase` ra state party
        self._workers = {}
        self._dung = threading.Event()
        self._th = None
        self.nhip_dem = 0
        self.viec_hien_tai = {}              # username -> viec (GUI doc)

    # -- chup anh --
    def chup(self):
        """Doc trang thai THAT cua tung client tai MOT khoanh khac.

        Doc THANG `client` (cung tien trinh) chu khong doi ai bao cao - L2. Loi khi doc mot acc
        KHONG duoc lam hong ca anh: coi acc do la `song=False`, nhip sau doc lai.
        """
        accs = []
        for username, c, la_leader in self._doc_clients():
            try:
                song = bool(getattr(c, "running", False))
                accs.append(AnhAcc(
                    username,
                    la_leader=la_leader,
                    song=song,
                    map_id=(int(getattr(c, "current_map", 0) or 0) or None) if song else None,
                    kenh=(int(getattr(c, "current_channel", 0) or 0) or None) if song else None,
                    dang_danh=bool(song and _goi(c, "in_combat", False)),
                    so_member=len(getattr(c, "party_members", None) or ()),
                    viec_vat=bool(song and _goi(c, "dang_lam_viec_vat", False)),
                    viec_dang_lam=self.viec_hien_tai.get(username, VIEC_NGHI),
                    xong_chore=bool(getattr(c, "_pe_xong_chore", False)),
                    trong_dg=bool(song and _goi(c, "in_di_gioi", False)),
                    # Doc DONG HO SERVER (`digioi_minutes_live`), khong tu dem gio: acc co the da
                    # dung gio DG o may khac / phien truoc. Engine cu tung danh dau acc con nguyen
                    # 120/120 phut la "xong DG" vi doan bua (ca that 07/09 [chutam]).
                    con_gio_dg=bool(song and _goi(c, "digioi_minutes_live", 0)
                                    < self.gio_dg_toi_da),
                ))
            except Exception:
                accs.append(AnhAcc(username, la_leader=la_leader, song=False))
        return AnhParty(self.pidx, accs, can_bao_nhieu=self.can_bao_nhieu,
                        map_dich=self.map_dich, pha=self.pha,
                        co_spot=self._spot() is not None,
                        pb_doi_level=self._pb_doi_level())

    # -- mot nhip --
    def nhip(self):
        anh = self.chup()
        self._doi_pha_neu_het_gio_dg(anh)
        if anh.pha != self.pha:
            anh.pha = self.pha            # doi pha ngay trong nhip nay, khong cho them mot giay
        viec = quyet_dinh(anh)
        self.nhip_dem += 1
        for username, v in viec.items():
            w = self._workers.get(username)
            if w is None:
                continue
            if w.giao(v) and self._log is not None:
                self._log.info("[party %d] ENGINE: %s -> %s", self.pidx + 1, username, v)
        self.viec_hien_tai = dict(viec)
        if self._bao_gui is not None:
            # GUI doc "dang lam gi" qua `set_account_activity` - engine moi phai bao y nhu engine
            # cu, khong thi user MU 14 party (documents/ENGINE_PARTY_MOI.md muc 4).
            for username, v in viec.items():
                try:
                    self._bao_gui(username, "engine: %s" % v, v)
                except Exception:
                    pass
        return viec

    # -- vong doi --
    def start(self):
        for username, c, la_leader in self._doc_clients():
            try:
                c._pe_la_leader = bool(la_leader)
            except Exception:
                pass
            w = self._workers.get(username)
            if w is not None:
                # ACC ROT ROI RELOGIN -> `GameClient` MOI HOAN TOAN. Worker cu van tro vao client
                # CU DA CHET: no se goi ham tren mot socket dong, va acc do VINH VIEN khong nhan
                # duoc lenh nua - mot kieu "im lang" y het `luumuoi` ngay 15/09.
                if w.client is not c:
                    w.client = c
                    w.giao(VIEC_NGHI)      # bo viec dang lam tren client cu
                    if self._log is not None:
                        self._log.info("[party %d] ENGINE: %s da relogin -> gan client MOI cho worker",
                                       self.pidx + 1, username)
                continue
            w = AccWorker(username, c, self._lam_viec)
            self._workers[username] = w
            w.start()
        if self._th is None or not self._th.is_alive():
            self._dung.clear()
            self._th = threading.Thread(target=self._vong, name="engine-p%d" % (self.pidx + 1),
                                        daemon=True)
            self._th.start()

    def stop(self):
        self._dung.set()
        for w in self._workers.values():
            w.stop()

    def _vong(self):
        while not self._dung.is_set():
            t0 = time.time()
            try:
                self.nhip()
            except Exception:
                # Mot nhip no KHONG duoc giet engine: party se dung im vinh vien, dung cai L0 cam.
                if self._log is not None:
                    self._log.exception("[party %d] ENGINE: nhip loi -> bo qua, nhip sau lam lai",
                                        self.pidx + 1)
            cho = NHIP_SEC - (time.time() - t0)
            if cho > 0:
                self._dung.wait(cho)

    def _lam_viec(self, client, viec, con_lam):
        dich = None
        if viec == VIEC_VE_MAP:
            dich = self._map_dich_hien_tai()
        elif viec == VIEC_DOI_KENH:
            dich = self._kenh_dich_hien_tai()
        elif viec == VIEC_RA_SPOT:
            dich = self._spot()
        elif viec == VIEC_PB_DOI:
            dich = self._pb_doi_level()
        thi_hanh(client, viec, con_lam, dich=dich, log=self._log)

    def _map_dich_hien_tai(self):
        anh = self.chup()
        maps = anh.maps()
        if self.map_dich in maps:
            return self.map_dich
        return _map_dich(anh, [a for a in anh.accs if a.song and not a.viec_vat], maps)

    def _doi_pha_neu_het_gio_dg(self, anh):
        """CA PARTY het gio Di Gioi -> doi pha sang train. ENGINE MOI PHAI TU LAM VIEC NAY.

        Hai cho doi pha cua engine cu deu KHONG chay voi party engine moi:
            `run_account`        - engine moi khong chay kich ban nay (cua chan so 2)
            `_dieu_phoi_quyet`   - dieu phoi cu bi cam dung vao party engine moi (cua chan so 1)
        Thieu doan nay thi party het gio DG se ket o pha DG VINH VIEN: moi acc `con_gio_dg=False`
        -> `VIEC_NGHI` -> dung im mai mai. Dung cai L0 cam ("party hong thi phai gom lai BANG
        DUOC", khong co duong "dung im").

        DU PARTY moi doi pha: mot acc con gio ma ca party bo di train la no mat gio DG. Acc dang
        lam viec vat khong tinh (no o map khac la dung).
        """
        if self.pha != PHA_DG:
            return
        dem = [a for a in anh.accs if a.song and not a.viec_vat]
        if not dem:
            return
        if any(a.con_gio_dg or a.trong_dg for a in dem):
            return                        # con nguoi con gio / dang trong DG -> chua doi
        self.pha = PHA_TRAIN
        if self._ghi_pha is not None:
            try:
                self._ghi_pha(PHA_TRAIN)
            except Exception:
                pass
        if self._log is not None:
            self._log.warning("[party %d] ENGINE: ca party (%d acc) HET GIO Di Gioi -> doi pha TRAIN",
                              self.pidx + 1, len(dem))

    def _pb_doi_level(self):
        """Level PB to doi CON LUOT gan nhat, doc tu DONG HO SERVER cua leader.

        `team_dungeon_remaining` tinh tu `mission_steps[daily_flag]` - bang mission-step server gui
        (`0x18 sub 0x06`). KHONG tu dem luot da danh: acc co the da danh o may khac / phien truoc,
        va engine cu tung danh dau nham acc con nguyen luot la "da xong" chi vi doan bua.

        Chua co bang mission-step -> tra None (CHUA KET LUAN), khong phai "het luot".
        """
        if not self.pb_doi_levels:
            return None
        lead_cli = None
        for username, c, la_leader in self._doc_clients():
            if la_leader and getattr(c, "running", False):
                lead_cli = c
                break
        if lead_cli is None or not getattr(lead_cli, "mission_steps_loaded", False):
            return None
        for lv in self.pb_doi_levels:
            try:
                con = lead_cli.team_dungeon_remaining(int(lv))
            except Exception:
                con = None
            if con:
                return int(lv)
        return None

    def _spot(self):
        if self._doc_spot is None:
            return None
        try:
            sp = self._doc_spot()
        except Exception:
            return None
        return (int(sp[0]), int(sp[1])) if sp else None

    def _kenh_dich_hien_tai(self):
        k = self.chup().kenhs()
        return k[0] if k else None
