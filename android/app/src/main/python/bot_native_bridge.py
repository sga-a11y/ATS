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
    return [bytes(f) for f in result]
