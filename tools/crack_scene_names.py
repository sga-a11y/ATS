"""Crack scene_names.json (TEN MAP THEO GAME) tu gamedata Data/TextData_C.dat + SceneSet_C.dat.

Client KHONG luu ten map thang trong SceneSet_C.dat, chi luu ID CHUOI:
  SceneSet_C.dat : header [count u32] + count record FIXED 17 byte,
                   record = `[text_id u32 LE][map_id u16 LE][...11 byte con lai]`
  TextData_C.dat : header [count u32] + cac record noi tiep,
                   record = `[text_id u32 LE][len u16 LE][text UTF-16LE, len BYTE]`

=> ten map = TextData[SceneSet[map].text_id].

Hai file lay tu may (MuMu):
  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/TextData_C.dat  gamedata/Data/
  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Data/SceneSet_C.dat  gamedata/Data/

Chay: python tools/crack_scene_names.py   -> ghi scene_names.json {"12924": "Thang Tháp", ...}
"""
import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "scene_names.json")


def _find(name):
    """Tim file trong gamedata/Data/ (bo day du) roi gamedata/ (bo rut gon da commit)."""
    for rel in (("gamedata", "Data", name), ("gamedata", name)):
        p = os.path.join(ROOT, *rel)
        if os.path.isfile(p):
            return p
    raise SystemExit("Khong thay %s trong gamedata/Data/ hay gamedata/ - xem docstring de adb pull" % name)


def load_texts(path):
    d = open(path, "rb").read()
    out = {}
    off = 4                      # bo header count
    while off + 6 <= len(d):
        tid, ln = struct.unpack_from("<IH", d, off)
        off += 6
        if off + ln > len(d):
            break
        out[tid] = d[off:off + ln].decode("utf-16-le", "replace").rstrip("\x00")
        off += ln
    return out


def load_scenes(path):
    d = open(path, "rb").read()
    count = struct.unpack_from("<I", d, 0)[0]
    if count <= 0:
        return {}
    rec = (len(d) - 4) // count
    out = {}
    for i in range(count):
        text_id, map_id = struct.unpack_from("<IH", d, 4 + i * rec)
        if map_id:
            out[map_id] = text_id
    return out


def main():
    texts = load_texts(_find("TextData_C.dat"))
    scenes = load_scenes(_find("SceneSet_C.dat"))
    names = {}
    for map_id, text_id in scenes.items():
        name = texts.get(text_id)
        if name:
            names[str(map_id)] = name
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(names, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print("%d chuoi, %d scene -> %d ten map ghi ra %s"
          % (len(texts), len(scenes), len(names), os.path.basename(OUT)))


if __name__ == "__main__":
    main()
