import hmac, hashlib, json
from fastapi.testclient import TestClient
import wa_server as w

c = TestClient(w.app)
r = c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": w.VERIFY, "hub.challenge": "12345"})
assert r.status_code == 200 and r.text == "12345", (r.status_code, r.text)
print("handshake benar: ok")
r = c.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "salah", "hub.challenge": "12345"})
assert r.status_code == 403
print("verify token salah ditolak: ok")
body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
r = c.post("/webhook", content=body, headers={"x-hub-signature-256": "sha256=deadbeef"})
assert r.status_code == 403
print("tanda tangan palsu ditolak: ok")
sig = "sha256=" + hmac.new(w.APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
r = c.post("/webhook", content=body, headers={"x-hub-signature-256": sig})
assert r.status_code == 200
print("tanda tangan benar diterima: ok")
print("ALL OK")
