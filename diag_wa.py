import os, httpx
from dotenv import load_dotenv

load_dotenv(".env")
t = os.environ["WHATSAPP_ACCESS_TOKEN"]
v = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
pid = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
waba = os.environ["WHATSAPP_WABA_ID"]
secret = os.environ["WHATSAPP_APP_SECRET"]
APP_ID = "2293632888090163"  # dari URL dashboard app yang kamu tempel

print("panjang token:", len(t), "| awalan:", t[:3], "| jumlah 'EAA':", t.count("EAA"),
      "| ada spasi atau baris baru:", any(c.isspace() for c in t))
print("phone_number_id di .env :", pid, "| di webhook Meta: 1388984240971710")
print("waba_id di .env         :", waba, "| di webhook Meta: 1420955993446541")

r = httpx.get("https://graph.facebook.com/debug_token",
              params={"input_token": t, "access_token": f"{APP_ID}|{secret}"}, timeout=30).json()
if "error" in r:
    print("debug_token ERROR:", r["error"].get("message"))
else:
    d = r.get("data", {})
    print("debug_token:", {k: d.get(k) for k in ("is_valid", "type", "app_id", "expires_at", "scopes")})
    if d.get("error"):
        print("debug_token detail:", d["error"])

r2 = httpx.get(f"https://graph.facebook.com/{v}/{pid}",
               params={"fields": "display_phone_number,verified_name"},
               headers={"Authorization": "Bearer " + t}, timeout=30)
print("cek nomor:", r2.status_code, r2.text[:300])
