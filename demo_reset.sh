#!/usr/bin/env bash
# Clear demo transactions and pending confirmations for one WhatsApp number.
# Usage: ./demo_reset.sh [nomor]   (default: first number in WHATSAPP_ALLOWED_NUMBERS)
set -euo pipefail
cd "$(dirname "$0")"

NUMBER="${1:-$(grep '^WHATSAPP_ALLOWED_NUMBERS=' .env | cut -d= -f2 | cut -d, -f1 | tr -dc '0-9')}"
if [ -z "$NUMBER" ]; then
  echo "Nomor tidak ditemukan. Isi WHATSAPP_ALLOWED_NUMBERS di .env atau jalankan: ./demo_reset.sh 6285xxxx"
  exit 1
fi

DEMO_NUMBER="$NUMBER" .venv/bin/python - <<'PY'
from dotenv import load_dotenv; load_dotenv(".env")
import os
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
owner = sb.table("owners").select("id").eq("channel", "whatsapp").eq("external_id", os.environ["DEMO_NUMBER"]).execute().data
if not owner:
    raise SystemExit("Owner belum ada di database. Kirim satu pesan ke bot dulu.")
oid = owner[0]["id"]
sb.table("transactions").delete().eq("owner_id", oid).execute()
sb.table("pending_confirmations").delete().eq("owner_id", oid).execute()
print("demo data cleared for", oid)
PY
