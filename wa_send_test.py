import os, sys, httpx
from dotenv import load_dotenv

load_dotenv(".env")
v = os.environ.get("WHATSAPP_API_VERSION", "v21.0")
pid = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
to = "".join(c for c in sys.argv[1] if c.isdigit())
r = httpx.post(
    f"https://graph.facebook.com/{v}/{pid}/messages",
    headers={"Authorization": "Bearer " + os.environ["WHATSAPP_ACCESS_TOKEN"]},
    json={"messaging_product": "whatsapp", "to": to, "type": "text",
          "text": {"body": "Tes dari CatatAI (dikirim dari kode kita sendiri)."}},
    timeout=30)
print(r.status_code)
print(r.text[:400])
