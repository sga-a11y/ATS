"""Giai ma Lua client (TS Online Mobile) -> doc duoc bang text.

Nguon (KNOWLEDGE muc 'Da giai ma Lua'): LuaFileUtils.ReadFile goi CryptUtils.DeCrypt;
ProjectSetting.cctor cung cap AES/Rijndael CBC PKCS7 key `1234567870541704`, IV `7054170412345678`.

Keo cay Lua tu may (MuMu):
  adb pull /sdcard/Android/data/com.vtcmobile.gz06/files/Lua  <thu-muc>

Chay: python tools/decrypt_lua.py <thu-muc-lua-ma-hoa> <thu-muc-ra>
"""
import os
import sys

from Crypto.Cipher import AES

KEY = b"1234567870541704"
IV = b"7054170412345678"


def decrypt(data: bytes) -> bytes:
    if len(data) < 16:
        return data
    out = AES.new(KEY, AES.MODE_CBC, IV).decrypt(data[:len(data) // 16 * 16])
    pad = out[-1] if out else 0
    if 1 <= pad <= 16 and out.endswith(bytes([pad]) * pad):
        out = out[:-pad]
    return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    n = bad = 0
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if not fn.endswith(".lua"):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, src)
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            try:
                data = decrypt(open(p, "rb").read())
                open(out, "wb").write(data)
                n += 1
            except Exception as e:
                bad += 1
                print("LOI %s: %s" % (rel, e))
    print("da giai ma %d file (%d loi) -> %s" % (n, bad, dst))


if __name__ == "__main__":
    main()
