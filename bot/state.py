"""Theo doi trang thai tran dau: HP/SP cua char, pet, dong doi, quai.

Phan tich tu cac packet S2C:
  - 0x0b: full stats 1 entity (HP/SP max+cur)
  - 0x33: cap nhat HP/SP theo luot (block 03 02 = char, 03 01 = pet)
  - 0x0c: thong tin quai luc vao tran
"""
import struct
import logging
log = logging.getLogger("bot")

# Stat type trong 0x33 / 0x0b
T_HP_CUR = 0x19
T_SP_CUR = 0x1A
T_HP_MAX = 0xCD
T_SP_MAX = 0xCE   # maxSP - nam trong S2C 0x08 sub0300 (theo entity), KHONG phai 0x33


class Unit:
    def __init__(self, name=""):
        self.name = name
        self.hp = 0
        self.hp_max = 0
        self.sp = 0
        self.sp_max = 0

    @property
    def hp_pct(self):
        return self.hp / self.hp_max if self.hp_max else 1.0

    def __repr__(self):
        return f"{self.name}(HP={self.hp}/{self.hp_max} SP={self.sp}/{self.sp_max})"


class BattleState:
    def __init__(self):
        self.char = Unit("char")
        self.pet = Unit("pet")
        self.self_entity = None   # entity 8 byte cua nhan vat minh (set tu client)
        self.skills_char = []     # LIST skill char (tu 0x05 day du - giu thu tu: skill[0]=boss fallback)
        self.skills_pet  = set()  # skill ID pet co (tu 0x28 login)
        self.my_atype = 3         # atype = vi tri formation cua minh (leader o giua)
        self.label = ""           # nhan account (de tao key dieu phoi heal)
        self.party_idx = None     # index party (dieu phoi hoi sinh chéo account)
        self.pet_skills = []      # LIST skill cua pet dang dung (pets.json, giu thu tu - skill[0]=boss fallback)
        self.active_pet_id = None # id pet dang dung (tu S2C 0x13)
        self.boss_mode = False    # True = dang trong dungeon danh boss -> pet dung skill manh (tu suy)
        # SP DAY (sp==sp_max) luc nao trong tran -> spam combo CA TRAN, bat chap so quai (1 quai cung dung).
        self.char_spam = False
        self.pet_spam = False
        # dong doi trong party (entity_id -> Unit), khong gom char/pet cua minh.
        # maxHP+maxSP (char & pet) nap tu 0x0b full-stat (update_0x0b); cur HP/SP cap nhat tung luot 0x33.
        self.allies = {}
        # maxSP (b1,slot)->val tu 0x0b. BEN: allies bi clear MOI tran (0x34) nhung 0x0b party chi toi
        # luc spawn -> luu rieng de ko mat maxSP giua cac tran. Nguon duy nhat co pet maxSP.
        self.ally_spmax = {}
        self.mobs = []  # list HP_max cua quai (theo thu tu xuat hien)
        self.in_battle = False
        # vi tri quai con song (slot B2) - decode tu 0x33; dung lam target combat
        self.enemy_slots = []          # vd [2] = co 1 quai o slot 2
        self.enemy_hp = {}             # slot -> curHP
        self.self_slot = None          # B2 (vi tri tran) cua minh - tu 0x0b battle (entity-based)
        # QUEST mode: START tran ma >5 quai -> True ca tran (latch). >5 con -> all-target; <=5 -> nhu boss.
        self.quest_mode = False
        self._battle_counted = False   # latch: da dem so quai luc start tran chua
        # DEM THE HE du lieu quai: tang moi lan CO goi 0x33 THAT cap nhat nhom quai (saw_enemy_group).
        # Goi 0x35 (offer luot) KHONG mang du lieu quai -> neu 0x35 den ma KHONG co 0x33 moi kem theo
        # (vi du: tran da ket that nhung con offer "tan du" den tre) -> enemy_gen KHONG doi -> combat.py
        # se BO QUA (khong danh lai bang du lieu quai CU) thay vi danh mu/danh lai tren trang thai stale.
        self.enemy_gen = 0
        self.last_atk_gen_char = -1
        self.last_atk_gen_pet = -1
        # DI GIOI SOLO: toi da 4 pet ra tran CUNG LUC, moi con 1 atype RIENG (0,1,3,4 - atype 2 la
        # cua CHAR). KHAC han truong hop binh thuong (1 pet, dung state.pet + skills_pet chung voi
        # char). solo_multipet=True -> client.py dung nhanh combat rieng (combat.decide_multipet).
        self.solo_multipet = False
        self.multi_pet = {}          # atype (0,1,3,4) -> Unit (HP/SP tung pet, tu update_0x33)
        self.multi_pet_skills = {}   # atype -> [skill id] (tu pets.json, xem client._on_pet_list)
        self.last_atk_gen_multipet = {}   # atype -> enemy_gen da danh (tranh danh lap khi 0x33 cu)

    def reset_battle(self):
        self.mobs = []
        self.in_battle = False

    def reset_enemies(self, reset_quest=True):
        """Xoa HP/slot quai (goi luc battle moi bat dau, tranh dinh quai tran cu).
        reset_quest=False: GIU quest_mode/_battle_counted. 0x34 ban MOI TURN -> neu reset moi turn thi
        khi quai con <=5 se MAT latch quest_mode (set luc >5 dau tran) -> roi nham ve TRAIN mode.
        Chi reset khi la ENCOUNTER MOI (gap thoi gian lon giua 2 turn -> client.py quyet dinh)."""
        self.enemy_hp = {}
        self.enemy_slots = []
        if reset_quest:
            self.quest_mode = False
            self._battle_counted = False

    # ---- parse 0x33 (stat update theo luot) ----
    def update_0x33(self, pkt: bytes):
        """Block 7 byte: [00][B1][B2][type][val 2B LE][00].
          B1: 3=nhan vat, 2=pet, 0=QUAI(dich). B2: slot/vi tri (1..n).
          type: 0x19=curHP, 0x1a=SP, 0xcd=maxHP.
        -> lay danh sach quai (B1=0, curHP>0) de target; cap nhat HP/SP char/pet cua minh.
        """
        body = pkt[7:] if len(pkt) > 7 and pkt[6] == 0x33 else pkt
        # bo 2 byte prefix (01 00)
        p = body[2:]
        groups = {}  # (B1,B2) -> {type: val}
        i = 0
        while i + 7 <= len(p):
            a, b1, b2, tt = p[i], p[i + 1], p[i + 2], p[i + 3]
            # b1: 0=quai hang truoc, 1=quai hang sau, 2=pet, 3=nhan vat
            if a == 0x00 and b1 in (0x00, 0x01, 0x02, 0x03) and tt in (T_HP_CUR, T_SP_CUR, T_HP_MAX):
                val = int.from_bytes(p[i + 4:i + 6], "little")
                groups.setdefault((b1, b2), {})[tt] = val
                i += 7
            else:
                i += 1
        # QUAI = b1 in (0,1): hang truoc b1=0, hang sau b1=1; cot = b2.
        # Vi tri noi bo = b1*10 + b2 -> hang=pos//10, cot=pos%10 (gui combat: b=hang, target=cot)
        saw_enemy_group = False
        for (b1, b2), d in groups.items():
            if b1 in (0x00, 0x01):
                saw_enemy_group = True
                pos = b1 * 10 + b2
                self.enemy_hp[pos] = d.get(T_HP_CUR, 0)
        if saw_enemy_group:
            self.enemy_gen += 1   # co du lieu quai MOI that su -> danh gia lai duoc phep danh lai
            # enemy_slots = TAT CA slot con song theo enemy_hp TICH LUY (khong chi goi nay).
            # Tranh mat con khong bi danh trong turn (vd giet 1-2-3 con con o slot 7 van song).
            self.enemy_slots = sorted(s for s, hp in self.enemy_hp.items() if hp > 0)
            # LATCH quest_mode: dem so quai LUC START tran (lan dau thay quai). >5 -> QUEST ca tran.
            if not self._battle_counted and self.enemy_slots:
                self._battle_counted = True
                if len(self.enemy_slots) > 5:
                    self.quest_mode = True
        # DI GIOI SOLO: 4 pet CUNG LUC, moi con atype RIENG (b1=2, b2=atype - xac nhan qua capture
        # thuc te: b2 trong 0x33 CHINH LA atype dung de gui 0x32, KHONG can quy doi them). Cap nhat
        # RIENG cho tung atype, KHONG dua vao self_slot (self_slot chi ung voi pet DUY NHAT truong
        # hop binh thuong, sai hoan toan khi co 4 pet).
        if self.solo_multipet:
            for (b1, b2), d in groups.items():
                if b1 == 0x02:
                    u = self.multi_pet.get(b2)
                    if u is None:
                        u = Unit(f"pet_at{b2}")
                        self.multi_pet[b2] = u
                    if T_HP_MAX in d: u.hp_max = d[T_HP_MAX]
                    if T_HP_CUR in d: u.hp = d[T_HP_CUR]
                    if T_SP_CUR in d: u.sp = d[T_SP_CUR]
        # self_slot xac dinh tu 0x0b battle (entity-based, o client) hoac roster. KHONG dua HP.
        # Doc HP/SP char+pet cua minh theo slot (uu tien roster -> chinh xac, KHONG can 0x0b)
        if self.self_slot is not None:
            pd = groups.get((0x02, self.self_slot))
            if pd:
                if T_HP_MAX in pd: self.pet.hp_max = pd[T_HP_MAX]
                if T_HP_CUR in pd: self.pet.hp = pd[T_HP_CUR]
                if T_SP_CUR in pd: self.pet.sp = pd[T_SP_CUR]
            cd = groups.get((0x03, self.self_slot))
            if cd:
                if T_HP_MAX in cd: self.char.hp_max = cd[T_HP_MAX]
                if T_HP_CUR in cd: self.char.hp = cd[T_HP_CUR]
                if T_SP_CUR in cd: self.char.sp = cd[T_SP_CUR]
        # Cap nhat HP + SP TAT CA dong doi (char B1=3, pet B1=2 cua moi slot) -> de quyet dinh hoi mau/SP.
        # SP: 0x33 co T_SP_CUR cua MOI member (server gui ca party). sp_max = MAX SP da thay (dau tran
        # full SP -> bat dung max that), vi 0x33 khong mang maxSP (chi 0x0b cua RIENG minh co).
        for (b1, b2), d in groups.items():
            if b1 in (0x02, 0x03) and (T_HP_CUR in d or T_HP_MAX in d or T_SP_CUR in d):
                u = self.allies.get((b1, b2))
                if u is None:
                    u = Unit(f"{'char' if b1==3 else 'pet'}{b2}")
                    self.allies[(b1, b2)] = u
                if T_HP_MAX in d: u.hp_max = d[T_HP_MAX]
                if T_HP_CUR in d: u.hp = d[T_HP_CUR]
                if T_SP_CUR in d: u.sp = d[T_SP_CUR]   # maxSP nap tu 0x0b (update_0x0b)
                u.slot = b2

    # ---- parse 0x0b (full stats char/pet) ----
    def _read_0b_block(self, pkt, ent, b1, slot, who):
        """Block 0x0b: [entity 8B][10 byte][marker b1,slot][maxHP u32][maxSP u32][curHP][curSP].
        Anchor = ENTITY (duy nhat) -> marker o ent_idx+18. Tranh quet marker [b1][slot] truc tiep
        (slot=0 -> '03 00' qua pho bien -> khop nham -> maxSP rac nhu 244736)."""
        if not ent:
            return
        i = pkt.find(ent)
        while i != -1:
            m = i + 18   # marker o sau entity 8B + 10 byte
            if m + 18 <= len(pkt) and pkt[m] == b1 and pkt[m + 1] == slot:
                mh = struct.unpack_from("<I", pkt, m + 2)[0]
                ms = struct.unpack_from("<I", pkt, m + 6)[0]
                ch = struct.unpack_from("<I", pkt, m + 10)[0]
                cs = struct.unpack_from("<I", pkt, m + 14)[0]
                if 0 < mh < 1_000_000 and 0 < ms < 1_000_000 and ch <= mh and cs <= ms + 1:
                    who.hp_max, who.sp_max, who.hp, who.sp = mh, ms, ch, cs
                    return
            i = pkt.find(ent, i + 1)

    def update_0x0b(self, pkt: bytes):
        """MAX SP char+pet (0x33 chi co maxHP). CHAR anchor self_entity; PET anchor pet-entity
        (= active_pet_id 2B + 6 byte 00, vd 0xa05a -> 5a a0 00..). Marker o entity+18.
        (xac nhan spmax.pcap: char 454/208, pet 1194/339.)"""
        # 0x0b full-stat ca party: quet TOAN BO block char/pet (b1=2 pet, 3 char) cua MOI thanh vien
        # -> nap maxSP+maxHP dong doi theo (b1,slot). DAY la nguon DUY NHAT co pet maxSP (0x33/0x08
        # ko co). Validate 4 field (cur<=max...) tranh khop nham. Phu CA nguoi choi tay.
        # PHAI chay TRUOC guard self_slot (quet party ko can self_slot; goi party lon toi luc spawn
        # khi self_slot co the chua co -> neu return som se mat maxSP).
        if len(pkt) > 100:
            j = 0
            while j + 18 <= len(pkt):
                bb, sl = pkt[j], pkt[j + 1]
                if bb in (2, 3) and sl < 6:
                    mh, ms, ch, cs = struct.unpack_from("<IIII", pkt, j + 2)
                    if 50 < mh < 1_000_000 and 0 < ms < 100_000 and ch <= mh and cs <= ms + 1 and mh > ms:
                        u = self.allies.get((bb, sl))
                        if u is None:
                            u = Unit(f"{'char' if bb == 3 else 'pet'}{sl}")
                            self.allies[(bb, sl)] = u
                        u.hp, u.hp_max, u.sp, u.sp_max = ch, mh, cs, ms
                        u.slot = sl
                        self.ally_spmax[(bb, sl)] = ms   # BEN qua cac tran (allies bi clear)
                        j += 18
                        continue
                j += 1
        slot = self.self_slot
        if slot is None:
            return
        self._read_0b_block(pkt, self.self_entity, 3, slot, self.char)   # CHAR
        if self.active_pet_id:                                            # PET
            pe = self.active_pet_id.to_bytes(2, "little") + b"\x00" * 6
            self._read_0b_block(pkt, pe, 2, slot, self.pet)

    def lowest_hp_ally(self):
        """Unit (char/pet bat ky thanh vien) thap mau nhat - CHI con SONG (hp>0). None neu khong co.
        Con HP=0 da CHET -> bo qua (hoi mau vo dung)."""
        alive = [u for u in self.allies.values() if u.hp_max > 0 and u.hp > 0]
        if not alive:
            return None
        return min(alive, key=lambda u: u.hp_pct)

    def dead_allies(self):
        """List (b1, b2, hp_max) dong doi DA CHET (hp_max>0, hp<=0). b1=3 char/2 pet, b2=slot.
        Dung cho HOI SINH (target con chet)."""
        return [(b1, b2, u.hp_max) for (b1, b2), u in self.allies.items()
                if u.hp_max > 0 and u.hp <= 0]

    def any_ally_low(self, threshold: float):
        """Co thanh vien nao (char/pet) HP% <= threshold + CON SONG (hp>0) khong (gom ca minh).
        Con HP=0 da CHET -> KHONG tinh (hoi mau vo dung)."""
        for u in self.allies.values():
            if u.hp_max > 0 and u.hp > 0 and u.hp_pct <= threshold:
                return True
        return False

    def ally_low_sp(self, threshold: float, exclude):
        """Slot (b2) cua dong doi CON SONG co SP% < threshold, TRU caster (exclude=(b1,slot)).
        Tra slot de target skill hoi SP team; None neu khong co. Nhieu dua -> tra dua dau gap."""
        for (b1, b2), u in self.allies.items():
            if (b1, b2) == exclude:
                continue
            if u.hp <= 0:   # CHET roi -> bo qua
                continue
            smax = self.ally_spmax.get((b1, b2), u.sp_max)   # maxSP ben (allies bi clear moi tran)
            if smax > 0 and (u.sp / smax) < threshold:
                return b2
        return None
