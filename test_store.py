from store import *

o = get_owner("test", "store-test")
oid = o["id"]
try:
    # idempotency
    assert mark_processed("test:msg-1") is True
    assert mark_processed("test:msg-1") is False
    print("idempotency ok")

    # pending round trip
    save_pending(oid, "nota", "photo", {"hello": "dunia"})
    assert load_pending(oid)["payload"] == {"hello": "dunia"}
    clear_pending(oid)
    assert load_pending(oid) is None
    print("pending ok")

    # nota: owner corrected nasi putih 12000 -> 15000, so edited must be True
    original = {"type": "sale", "total": 84000, "items": [
        {"name": "Gurame goreng", "qty": 1, "unit_price": 65000, "subtotal": 65000, "confidence": 0.95},
        {"name": "nasi Putih", "qty": 1, "unit_price": 12000, "subtotal": 12000, "confidence": 0.95},
        {"name": "Kelapa muda", "qty": 1, "unit_price": 7000, "subtotal": 7000, "confidence": 0.95}]}
    final = {"type": "sale", "total": 87000, "adjustments": [], "items": [
        {"name": "Gurame goreng", "qty": 1, "unit_price": 65000, "subtotal": 65000, "confidence": 0.95},
        {"name": "nasi Putih", "qty": 1, "unit_price": 15000, "subtotal": 15000, "confidence": 1.0},
        {"name": "Kelapa muda", "qty": 1, "unit_price": 7000, "subtotal": 7000, "confidence": 0.95}]}
    save_nota(oid, final, original)

    # voice: 2 sales (one without price) and 2 purchases (one without price)
    entries = [
        {"type": "sale", "name": "es teh", "qty": 10, "unit": "gelas", "unit_price": 500, "subtotal": 5000, "confidence": 0.95},
        {"type": "sale", "name": "kopi susu", "qty": 12, "unit": None, "unit_price": None, "subtotal": None, "confidence": 0.95},
        {"type": "purchase", "name": "gula", "qty": 2, "unit": "kilo", "unit_price": 14000, "subtotal": 28000, "confidence": 0.95},
        {"type": "purchase", "name": "susu", "qty": 3, "unit": "liter", "unit_price": None, "subtotal": None, "confidence": 0.95}]
    save_voice(oid, entries, {"entries": entries})

    rows = sb.table("transactions").select("type,source,edited,total_mismatch_confirmed,total").eq("owner_id", oid).execute().data
    for r in rows:
        print(r)
    assert any(r["edited"] for r in rows if r["source"] == "photo")

    s = summary_data(oid)
    assert (s["revenue"], s["expenses"], s["unpriced"]) == (92000, 28000, 2), s
    print("\n" + summary_text(s, "id") + "\n")
    print(summary_text(s, "en"))
    print("\nALL OK")
finally:
    sb.table("owners").delete().eq("id", oid).execute()
    sb.table("processed_messages").delete().eq("message_id", "test:msg-1").execute()
    print("cleanup ok")
