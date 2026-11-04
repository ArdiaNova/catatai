import os, json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from supabase import create_client
from core import rp, validate, MODEL

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
TZ = ZoneInfo("Asia/Jakarta")

def today():
    return datetime.now(TZ).date()

def nota_date(d):
    """Use the date written on the nota when it is plausible, else today."""
    raw = (d or {}).get("date")
    if isinstance(raw, str) and raw.strip():
        try:
            day = datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return today()
        if today() - timedelta(days=365 * 5) <= day <= today() + timedelta(days=1):
            return day
    return today()

def _int(x):
    try:
        return None if x is None else int(round(float(x)))
    except (TypeError, ValueError):
        return None

# ---- owners ----
def get_owner(channel, external_id):
    r = sb.table("owners").select("*").eq("channel", channel).eq("external_id", external_id).limit(1).execute().data
    if r:
        return r[0]
    return sb.table("owners").insert({"channel": channel, "external_id": external_id}).execute().data[0]

def set_language(owner_id, lang):
    sb.table("owners").update({"language": lang}).eq("id", owner_id).execute()

# ---- idempotency (pass "<channel>:<message_id>") ----
def mark_processed(message_id):
    try:
        sb.table("processed_messages").insert({"message_id": message_id}).execute()
        return True
    except Exception as e:
        if "23505" in str(e) or "duplicate" in str(e).lower():
            return False
        raise

# ---- pending confirmations ----
def save_pending(owner_id, kind, source, payload):
    now = datetime.now(timezone.utc)
    sb.table("pending_confirmations").upsert({
        "owner_id": owner_id, "kind": kind, "source": source, "payload": payload,
        "updated_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat(),
    }, on_conflict="owner_id").execute()

def clear_pending(owner_id):
    sb.table("pending_confirmations").delete().eq("owner_id", owner_id).execute()

def load_pending(owner_id):
    r = sb.table("pending_confirmations").select("*").eq("owner_id", owner_id).limit(1).execute().data
    if not r:
        return None
    p = r[0]
    if datetime.fromisoformat(p["expires_at"]) < datetime.now(timezone.utc):
        clear_pending(owner_id)
        return None
    return p

# ---- model call log (never breaks the flow) ----
def log_call(owner_id, flow, meta, ok=True):
    try:
        sb.table("model_calls").insert({
            "owner_id": owner_id, "flow": flow, "model": MODEL,
            "latency_ms": int(float((meta or {}).get("latency_s") or 0) * 1000),
            "tokens_in": (meta or {}).get("tokens_in"), "tokens_out": (meta or {}).get("tokens_out"), "ok": ok,
        }).execute()
    except Exception:
        pass

# ---- saving confirmed transactions ----
def _core_view(d):
    items = [(str(i.get("name")), i.get("qty"), _int(i.get("unit_price")), _int(i.get("subtotal"))) for i in (d.get("items") or [])]
    return json.dumps({"items": items, "total": _int(d.get("total"))}, sort_keys=True, default=str)

def is_edited(data, original):
    return _core_view(data) != _core_view(original)

def _insert_tx(owner_id, type_, source, total, items, original, edited, mismatch, tx_date=None):
    tx = sb.table("transactions").insert({
        "owner_id": owner_id, "type": type_, "tx_date": (tx_date or today()).isoformat(), "total": total,
        "source": source, "original_extraction": original, "edited": edited,
        "total_mismatch_confirmed": mismatch,
    }).execute().data[0]
    rows = [{"transaction_id": tx["id"], "name": str(i.get("name") or "?"), "qty": i.get("qty"), "unit": i.get("unit"),
             "unit_price": _int(i.get("unit_price")), "subtotal": _int(i.get("subtotal")),
             "confidence": i.get("confidence")} for i in items]
    if rows:
        try:
            sb.table("transaction_items").insert(rows).execute()
        except Exception:
            sb.table("transactions").delete().eq("id", tx["id"]).execute()
            raise
    return tx["id"]

def save_nota(owner_id, data, original, source="photo"):
    v = validate(data)
    t = data.get("type") if data.get("type") in ("sale", "purchase") else "unknown"
    return _insert_tx(owner_id, t, source, _int(data.get("total")), data.get("items") or [],
                      original, is_edited(data, original), not v["total_ok"], tx_date=nota_date(data))

def save_voice(owner_id, entries, original, edited=False, source="voice"):
    ids = []
    for t in ("sale", "purchase", "unknown"):
        grp = [e for e in entries if (e.get("type") if e.get("type") in ("sale", "purchase") else "unknown") == t]
        if not grp:
            continue
        known = [_int(e.get("subtotal")) for e in grp if e.get("subtotal") is not None]
        ids.append(_insert_tx(owner_id, t, source, sum(known) if known else None, grp, original, edited, False))
    return ids

# ---- daily summary ----
def summary_data(owner_id, day=None):
    day = day or today()
    rows = sb.table("transactions").select("type,total,transaction_items(name,qty,unit,subtotal)") \
        .eq("owner_id", owner_id).eq("tx_date", day.isoformat()).execute().data
    revenue = sum((r["total"] or 0) for r in rows if r["type"] == "sale")
    expenses = sum((r["total"] or 0) for r in rows if r["type"] == "purchase")
    unpriced, sold = 0, {}
    for r in rows:
        for it in r["transaction_items"]:
            if it["subtotal"] is None:
                unpriced += 1
            if r["type"] == "sale":
                k = (it["name"] or "?").strip().lower()
                sold[k] = sold.get(k, 0) + float(it["qty"] or 0)
    top = sorted(sold.items(), key=lambda kv: -kv[1])[:3]
    return {"day": day, "n": len(rows), "revenue": revenue, "expenses": expenses,
            "profit": revenue - expenses, "unpriced": unpriced, "top": top}

def summary_text(s, lang="id"):
    d = s["day"].strftime("%d-%m-%Y")
    if lang == "en":
        if not s["n"]:
            return f"No transactions logged on {d}."
        out = [f"Summary {d}:", f"Sales: {rp(s['revenue'])}", f"Purchases: {rp(s['expenses'])}",
               f"Estimated profit (sales - purchases): {rp(s['profit'])}"]
        if s["top"]:
            out.append("Top sellers: " + ", ".join(f"{n} ({q:g})" for n, q in s["top"]))
        if s["unpriced"]:
            out.append(f"⚠️ {s['unpriced']} items have no price yet and are not counted.")
        return "\n".join(out)
    if not s["n"]:
        return f"Belum ada transaksi tercatat pada {d}."
    out = [f"Ringkasan {d}:", f"Penjualan: {rp(s['revenue'])}", f"Pembelian: {rp(s['expenses'])}",
           f"Estimasi untung (penjualan - pembelian): {rp(s['profit'])}"]
    if s["top"]:
        out.append("Terlaris: " + ", ".join(f"{n} ({q:g})" for n, q in s["top"]))
    if s["unpriced"]:
        out.append(f"⚠️ {s['unpriced']} item belum ada harga, belum dihitung.")
    return "\n".join(out)


def latest_tx_date(owner_id):
    r = sb.table("transactions").select("tx_date").eq("owner_id", owner_id) \
        .order("tx_date", desc=True).limit(1).execute().data
    if not r:
        return None
    try:
        return datetime.strptime(str(r[0]["tx_date"])[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def summary_reply(owner_id, lang="id"):
    """Today's summary; when today is empty, fall back to the latest day with data."""
    today_s = summary_data(owner_id)
    if today_s["n"]:
        return summary_text(today_s, lang)
    last = latest_tx_date(owner_id)
    if not last or last == today_s["day"]:
        return summary_text(today_s, lang)
    prefix = ("Tidak ada transaksi hari ini. " if lang == "id"
              else "No transactions today. ")
    return prefix + summary_text(summary_data(owner_id, last), lang)
