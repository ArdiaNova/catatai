#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
pkill -f "uvicorn wa_server" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1
: > wa_server.log; : > tunnel.log
PYTHONUNBUFFERED=1 uvicorn wa_server:app --host 127.0.0.1 --port 8000 --no-access-log >> wa_server.log 2>&1 &
UV=$!
cloudflared tunnel --url http://localhost:8000 >> tunnel.log 2>&1 &
CF=$!
trap 'echo; echo "Menghentikan server dan tunnel..."; kill $UV $CF 2>/dev/null; exit 0' INT TERM
URL=""
for i in $(seq 1 40); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then echo "Alamat tunnel belum muncul. Lihat tunnel.log"; kill $UV $CF 2>/dev/null; exit 1; fi
echo "=================================================="
echo "Callback URL : $URL/webhook"
echo "Verify token : $(grep '^WHATSAPP_VERIFY_TOKEN=' .env | cut -d= -f2)"
echo "=================================================="
echo "Ctrl+C untuk menghentikan. Pesan masuk akan muncul di bawah:"
tail -n 0 -f wa_server.log
