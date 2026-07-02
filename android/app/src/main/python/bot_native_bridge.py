"""Cau noi Python (Chaquopy) -> protocol-native (C++) qua JNI. Python KHONG tu lam XOR/frame
nua - moi thu di qua ProtocolBridge (Kotlin) de mac dinh dung 1 nguon that duy nhat, tranh
lech logic giua 2 ngon ngu (day la lop bao ve chinh cho giao thuc)."""
from java import jclass


def _bridge():
    return jclass("com.tsbot.android.ProtocolBridge")


def encode_frame(opcode: int, payload: bytes) -> bytes:
    result = _bridge().INSTANCE.encodeFrame(opcode, bytearray(payload))
    return bytes(result)


def decode_stream(wire_buf: bytes):
    result = _bridge().INSTANCE.decodeStream(bytearray(wire_buf))
    # Dung size()/get(i) thay vi "for f in result": mot so kieu java.util.List
    # (vd Collections$SingletonList khi Kotlin Array.toList() tra ve 1 phan tu)
    # khong duoc Chaquopy proxy iterable truc tiep, nhung size()/get() luon dung.
    return [bytes(result.get(i)) for i in range(result.size())]
