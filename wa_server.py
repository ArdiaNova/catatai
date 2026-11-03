import os, hmac, hashlib, json
import httpx
from fastapi import FastAPI, Request, Response, BackgroundTasks
from dotenv import load_dotenv
import voice
from agent import handle

load_dotenv(".env")
TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
PHONE_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
APP_SECRET = os.environ["WHATSAPP_APP_SECRET"]
VERIFY = os.environ["WHATSAPP_VERIFY_TOKEN"]
V = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
ALLOWED = {"".join(c for c in x if c.isdigit()) for x in os.environ.get("WHATSAPP_ALLOWED_NUMBERS", "").split(",") if x.strip()}
G = f"https://graph.facebook.com/{V}"
AUTH = {"Authorization": "Bearer " + TOKEN}
app = FastAPI()

def mask(n):
    return "***" + n[-4:] if n else "?"

def sig_ok(raw, header):
    algo, _, sig = (header or "").partition("=")
    if algo != "sha256" or not sig:
        return False
    expected = hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), sig.encode())

def send_text(to, text):
    for i in range(0, len(text), 3900):
        r = httpx.post(f"{G}/{PHONE_ID}/messages", headers=AUTH, timeout=30,
                       json={"messaging_product": "whatsapp", "to": to, "type": "text",
                             "text": {"body": text[i:i + 3900]}})
        if r.status_code != 200:
            print(f"[wa kirim gagal] {r.status_code} {r.text[:200]}")
            break
        try:
            mid = (r.json().get("messages") or [{}])[0].get("id")
        except Exception:
            mid = None
        print(f"[wa kirim] ke=***{to[-4:]} bagian={i // 3900 + 1} status={r.status_code} id={mid}")

def fetch_media(media_id):
    r = httpx.get(f"{G}/{media_id}", headers=AUTH, timeout=30)
    r.raise_for_status()
    d = httpx.get(r.json()["url"], headers=AUTH, timeout=60, follow_redirects=True)
    d.raise_for_status()
    return d.content

def process(msg):
    sender = msg.get("from") or ""
    digits = "".join(c for c in sender if c.isdigit())
    t = msg.get("type")
    print(f"[wa masuk] dari={mask(digits)} jenis={t} diizinkan={digits in ALLOWED}")
    if not digits or digits not in ALLOWED:
        return
    try:
        kw = {}
        if t == "text":
            kind, kw["text"] = "text", msg["text"]["body"]
        elif t == "image":
            kind, kw["image"] = "photo", fetch_media(msg["image"]["id"])
        elif t == "audio":
            kind = "voice"
            kw["audio"] = voice.to_wav(fetch_media(msg["audio"]["id"]))
        else:
            send_text(digits, "Maaf, jenis pesan ini belum didukung. Kirim teks, foto nota, atau voice note.")
            return
        reply = handle("whatsapp", digits, msg.get("id"), kind, **kw)
    except Exception as e:
        print("[wa error]", type(e).__name__, str(e)[:200])
        reply = "Maaf, ada kendala. Coba kirim ulang sebentar lagi."
    if reply:
        send_text(digits, reply)

@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    ok = q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", "").encode(), VERIFY.encode())
    print("[wa verifikasi]", "ok" if ok else "DITOLAK", flush=True)
    if ok:
        return Response(content=q.get("hub.challenge", ""), media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def receive(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    if not sig_ok(raw, request.headers.get("x-hub-signature-256")):
        print("[wa] tanda tangan tidak valid, ditolak")
        return Response(status_code=403)
    try:
        data = json.loads(raw)
    except ValueError:
        return Response(status_code=400)
    for entry in data.get("entry", []):
        for ch in entry.get("changes", []):
            value = ch.get("value") or {}
            for st in value.get("statuses") or []:
                print(f"[wa status] ke=***{(st.get('recipient_id') or '')[-4:]} status={st.get('status')} "
                      f"id={st.get('id')} err={st.get('errors')}")
            for msg in value.get("messages", []) or []:
                bg.add_task(process, msg)
    return Response(status_code=200)

@app.get("/privacy")
def privacy():
    html = """<!doctype html>
<html lang="id">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kebijakan Privasi CatatAI</title>
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6;color:#222}h1{font-size:1.6rem}h2{font-size:1.1rem;margin-top:1.6rem}</style>
</head>
<body>
<h1>Kebijakan Privasi CatatAI</h1>
<p>CatatAI adalah asisten back-office WhatsApp untuk UMKM. Kebijakan ini menjelaskan data yang kami proses.</p>
<h2>Data yang diproses</h2>
<ul>
<li>Pesan teks yang Anda kirim ke nomor CatatAI.</li>
<li>Foto nota atau dokumen yang Anda kirim.</li>
<li>Voice note yang Anda kirim.</li>
<li>Nomor WhatsApp Anda dan catatan transaksi yang dihasilkan.</li>
</ul>
<h2>Tujuan</h2>
<p>Data diproses untuk mengekstrak item transaksi, menyimpan catatan penjualan/pembelian, dan menampilkan ringkasan kepada pemilik usaha.</p>
<h2>Penyimpanan dan pemrosesan</h2>
<p>Data disimpan di Supabase. Ekstraksi menggunakan model AI Meta. Data tidak dijual dan tidak dipakai untuk iklan.</p>
<h2>Publikasi dan demo</h2>
<p>Untuk publikasi atau demo, data pribadi disamarkan (redaksi). Data asli hanya dipakai untuk evaluasi internal.</p>
<h2>Retensi dan penghapusan</h2>
<p>Data disimpan selama diperlukan untuk operasional. Anda dapat meminta penghapusan data dengan menghubungi kami.</p>
<h2>Kontak</h2>
<p>Email: ninoptimize@gmail.com</p>
<p>Terakhir diperbarui: 4 November 2026.</p>
</body>
</html>"""
    return Response(content=html, media_type="text/html")

@app.get("/health")
def health():
    return {"ok": True}
