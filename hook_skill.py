"""Hook goi TCP gui di (C2S) khi choi game thu cong tren MuMu.
Ghi lai tat ca packet game (da XOR decode) va log ra man hinh.

Chay: python hook_skill.py
Trong game: dung skill thu cong -> xem packet C2S 0x32 in ra.
"""
import frida
import sys
import struct
import time

DEVICE_ID   = "127.0.0.1:7555"
PACKAGE     = "com.vtcmobile.gz06"
XOR_KEY     = 0xAD
GAME_PORT   = 6614

JS = r"""
// Hook send() / write() syscall de bat packet TCP C2S (game -> server)
// Unity game dung cac bien the cua send(): send, sendto, SSL_write...
// Ta hook lop thap: send() trong libc

var send_fn = Module.findExportByName("libc.so", "send");
if (!send_fn) send_fn = Module.findExportByName("libc.so", "write");

if (send_fn) {
    Interceptor.attach(send_fn, {
        onEnter: function(args) {
            var fd   = args[0].toInt32();
            var buf  = args[1];
            var len  = args[2].toInt32();
            if (len < 7 || len > 4096) return;

            // Doc bytes de kiem tra magic XOR (c0^AD=6d, 91^AD=3c)
            try {
                var b0 = buf.readU8();
                var b1 = ptr(buf).add(1).readU8();
                // magic sau XOR: 0xc0^0xAD=0x6d, 0x91^0xAD=0x3c
                if (b0 !== 0x6d || b1 !== 0x3c) return;

                var raw = buf.readByteArray(len);
                send({type: 'pkt', len: len}, raw);
            } catch(e) {}
        }
    });
    send({type: 'status', msg: 'Hook send() OK'});
} else {
    send({type: 'status', msg: 'KHONG tim thay send() trong libc!'});
}
"""

def xor(data):
    return bytes(b ^ XOR_KEY for b in data)

def parse_packet(raw):
    data = xor(raw)
    if len(data) < 7:
        return None
    if data[0] != 0xc0 or data[1] != 0x91:
        return None
    plen = struct.unpack_from('<H', data, 2)[0]
    if plen != len(data):
        return None
    opcode  = data[6]
    payload = data[7:]
    return opcode, payload

def on_message(msg, data):
    if msg['type'] != 'send':
        return
    p = msg['payload']
    if p['type'] == 'status':
        print(f"[Frida] {p['msg']}")
        return
    if p['type'] != 'pkt' or not data:
        return

    result = parse_packet(bytes(data))
    if not result:
        return
    opcode, payload = result

    ts = time.strftime('%H:%M:%S')
    print(f"{ts} C2S op=0x{opcode:02x} len={len(payload)} | {payload.hex()}")

    # Giai thich cac opcode quan trong
    if opcode == 0x32 and len(payload) >= 10:
        unit       = payload[2]
        atype      = payload[3]
        b_flag     = payload[4]
        target     = payload[5]
        skill_id   = struct.unpack_from('<H', payload, 6)[0]
        unit_name  = 'CHAR' if unit == 3 else ('PET' if unit == 2 else f'unit{unit}')
        print(f"  >> COMBAT: {unit_name} atype={atype} b={b_flag} target={target} skill={skill_id}")
    elif opcode == 0x41:
        print(f"  >> ENTER BATTLE (solo/leader)")
    elif opcode == 0x0a:
        pass  # heartbeat, bo qua
    elif opcode == 0x44:
        if len(payload) >= 4:
            city_id = struct.unpack_from('<H', payload, 2)[0]
            print(f"  >> TELEPORT city_id={city_id}")


def main():
    print(f"[*] Ket noi Frida toi 127.0.0.1:27042 (qua adb forward)...")
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    # Tim PID tu danh sach process
    procs = dev.enumerate_processes()
    pid = None
    for p in procs:
        if PACKAGE in p.name:
            pid = p.pid
            break
    if pid is None:
        # Fallback: lay tu adb ps
        import subprocess, re
        adb = r"C:\LDPlayer\LDPlayer9\adb.exe"
        out = subprocess.check_output([adb, '-s', DEVICE_ID, 'shell', 'ps -A'], text=True, errors='ignore')
        m = re.search(r'\S+\s+(\d+).*' + re.escape(PACKAGE), out)
        if m:
            pid = int(m.group(1))
    if pid is None:
        print(f"[!] Khong tim thay process {PACKAGE}. Game co dang chay khong?")
        return
    print(f"[*] Attach vao {PACKAGE} (PID={pid})...")
    session = dev.attach(pid)
    script  = session.create_script(JS)
    script.on('message', on_message)
    script.load()
    print("[*] Dang hook... Dung skill trong game de xem packet. Ctrl+C de dung.\n")
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        pass
    session.detach()
    print("\n[*] Da dung.")

if __name__ == '__main__':
    main()
