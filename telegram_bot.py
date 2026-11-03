import os, time, shutil, fcntl, httpx
from datetime import datetime
from dotenv import load_dotenv
from agent import handle
import voice

load_dotenv()
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
FILE = f"https://api.telegram.org/file/bot{TOKEN}"
ALLOWED = {x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip()}
http = httpx.Client(timeout=70)

def call(method, **kw):
    r = http.post(f"{API}/{method}", json=kw).json()
    if not r.get("ok"):
        print(f"[telegram error] {method}: {r.get('error_code')} {r.get('description')}")
    return r

def send(chat_id, text):
    for i in range(0, len(text), 3900):
        call("sendMessage", chat_id=chat_id, text=text[i:i + 3900])

def download(file_id):
    path = http.get(f"{API}/getFile", params={"file_id": file_id}).json()["result"]["file_path"]
    return http.get(f"{FILE}/{path}").content

def process(m):
    chat_id = str(m["chat"]["id"])
    kind_log = "photo" if m.get("photo") else "voice" if (m.get("voice") or m.get("audio")) else "text" if m.get("text") else "other"
    print(f"[masuk] chat={chat_id} jenis={kind_log} diizinkan={chat_id in ALLOWED}")
    if chat_id not in ALLOWED:
        send(chat_id, f"Chat ID kamu: {chat_id}. Tambahkan ke TELEGRAM_ALLOWED_IDS di .env lalu jalankan ulang bot.")
        return
    try:
        kw = {}
        if m.get("photo"):
            kind, kw["image"] = "photo", download(m["photo"][-1]["file_id"])
        elif m.get("document") and str(m["document"].get("mime_type", "")).startswith("image/"):
            kind, kw["image"] = "photo", download(m["document"]["file_id"])
        elif m.get("voice") or m.get("audio"):
            kind = "voice"
            kw["audio"] = voice.to_wav(download((m.get("voice") or m.get("audio"))["file_id"]))
            if os.environ.get("SAVE_VOICE_SAMPLES") == "1":
                os.makedirs("samples", exist_ok=True)
                with open(f"samples/voice_{datetime.now():%H%M%S}_{m['message_id']}.wav", "wb") as f:
                    f.write(kw["audio"])
        elif m.get("text"):
            kind, kw["text"] = "text", m["text"]
        else:
            return
        if kind in ("photo", "voice"):
            call("sendChatAction", chat_id=chat_id, action="typing")
        reply = handle("telegram", chat_id, f"{chat_id}:{m['message_id']}", kind, **kw)
    except Exception as e:
        print("error:", type(e).__name__, str(e)[:200])
        reply = "Maaf, ada kendala. Coba kirim ulang sebentar lagi."
    if reply:
        send(chat_id, reply)

def main():
    lock = open("/tmp/catatai_bot.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("Sudah ada proses bot lain yang berjalan. Jalankan 'pkill -f telegram_bot.py', tunggu 5 detik, lalu coba lagi.")
    me = call("getMe")
    if not me.get("ok"):
        raise SystemExit("Token tidak valid. Isi ulang TELEGRAM_BOT_TOKEN di .env.")
    print(f"Bot @{me['result']['username']} terhubung. Izin: {sorted(ALLOWED) or 'belum ada'}")
    if not shutil.which("ffmpeg"):
        print("PERINGATAN: ffmpeg tidak ditemukan, voice note tidak bisa diproses.")
    print("Menyiapkan koneksi ke Telegram... (bisa sampai 30 detik)")
    offset, ready, polls = None, False, 0
    while True:
        params = {"timeout": 30 if ready else 0}
        if offset is not None:
            params["offset"] = offset
        try:
            r = http.post(f"{API}/getUpdates", json=params).json()
        except Exception as e:
            print("poll error:", type(e).__name__)
            time.sleep(3)
            continue
        if not r.get("ok"):
            if r.get("error_code") == 409:
                print("[menunggu] koneksi lama masih terbuka di Telegram, mencoba lagi...")
            else:
                print(f"[telegram error] getUpdates: {r.get('error_code')} {r.get('description')}")
            time.sleep(3)
            continue
        if not ready:
            ready = True
            print("=" * 56)
            print(f"SIAP {datetime.now():%H:%M:%S}: bot menerima teks, foto nota, dan voice note.")
            print("=" * 56)
            for cid in ALLOWED:
                send(cid, "✅ CatatAI siap. Kamu bisa kirim teks, foto nota, atau voice note.")
        polls += 1
        if polls % 10 == 0:
            print(f"[hidup {datetime.now():%H:%M:%S}] menunggu pesan...")
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            if u.get("message"):
                process(u["message"])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot dihentikan.")
