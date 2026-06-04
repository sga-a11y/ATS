import mitmproxy.http
from mitmproxy import ctx
import json, time, os

LOG_FILE = "traffic/traffic_raw.log"
os.makedirs("traffic", exist_ok=True)

class TSOnlineCapture:
    def __init__(self):
        self.count = 0
        ctx.log.info("=== TS Online Traffic Capture Started ===")

    def request(self, flow: mitmproxy.http.HTTPFlow):
        entry = {
            "time": time.time(),
            "type": "REQUEST",
            "method": flow.request.method,
            "url": flow.request.pretty_url,
            "host": flow.request.host,
            "headers": dict(flow.request.headers),
            "body_hex": flow.request.content.hex() if flow.request.content else "",
            "body_text": flow.request.text if flow.request.content else ""
        }
        self._log(entry)

    def response(self, flow: mitmproxy.http.HTTPFlow):
        entry = {
            "time": time.time(),
            "type": "RESPONSE",
            "url": flow.request.pretty_url,
            "status": flow.response.status_code,
            "headers": dict(flow.response.headers),
            "body_hex": flow.response.content.hex() if flow.response.content else "",
            "body_text": flow.response.text if flow.response.content else ""
        }
        self._log(entry)
        self.count += 1
        if self.count % 10 == 0:
            ctx.log.info(f"Captured {self.count} responses so far...")

    def _log(self, entry):
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

addons = [TSOnlineCapture()]
