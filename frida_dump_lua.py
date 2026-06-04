"""Dump Lua da giai ma tu memory game qua Frida (memory scan, khong can hook module)."""
import frida, sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 16266
OUTDIR = "E:/Claude/ATS/lua_dump"
os.makedirs(OUTDIR, exist_ok=True)

dev = frida.get_usb_device()
session = dev.attach(PID)

JS = r"""
// Tim cac vung memory chua chunk Lua, dump ve host
var ranges = Process.enumerateRanges('rw-');
var found = [];
ranges.forEach(function(r){
  try {
    var hits = Memory.scanSync(r.base, r.size, '2e 6c 75 61'); // ".lua"
    if (hits.length > 0) {
      found.push({base: r.base, size: r.size, n: hits.length});
    }
  } catch(e){}
});
send({stage:'scan', count: found.length, regions: found.map(function(f){
  return {base: f.base.toString(), size: f.size, n: f.n};
})});

// Dump theo chunk 1MB (Frida 17: dung ptr.readByteArray)
var CHUNK = 1024*1024;
found.forEach(function(f){
  var off = 0;
  while (off < f.size) {
    var sz = Math.min(CHUNK, f.size - off);
    try {
      var p = f.base.add(off);
      var data = p.readByteArray(sz);
      send({stage:'dump', base: f.base.toString(), off: off, size: sz}, data);
    } catch(e){
      send({stage:'err', base: f.base.toString(), off: off, msg: e.message});
    }
    off += sz;
  }
});
send({stage:'done'});
"""

script = session.create_script(JS)
done = {"v": False}

def on_message(msg, data):
    if msg["type"] != "send":
        print("ERR", msg)
        return
    p = msg["payload"]
    st = p.get("stage")
    if st == "scan":
        print(f"Tim thay {p['count']} region co '.lua'")
        for r in p["regions"]:
            print(f"  base={r['base']} size={r['size']} hits={r['n']}")
    elif st == "dump" and data:
        fn = os.path.join(OUTDIR, "region_" + p["base"] + ".bin")
        with open(fn, "ab") as f:   # append cac chunk
            f.write(data)
    elif st == "err":
        print("  dump err", p["base"], p["msg"])
    elif st == "done":
        done["v"] = True

script.on("message", on_message)
script.load()

t0 = time.time()
while not done["v"] and time.time() - t0 < 120:
    time.sleep(0.5)
print("Xong.")
