import json, re, sys
from core import client, MODEL, parse, validate, message, rp

YES = {"ya", "y", "iya", "yap", "yup", "yes", "betul", "benar", "bener", "ok", "oke",
       "sip", "siap", "sudah", "udah", "lanjut", "simpan", "correct", "right"}
NO = {"tidak", "tak", "enggak", "gak", "nggak", "bukan", "batal", "cancel", "no",
      "salah", "jangan", "belum"}

TYPE_WORDS = {
    "jual": "sale", "jualan": "sale", "penjualan": "sale", "terjual": "sale", "sale": "sale",
    "beli": "purchase", "belian": "purchase", "pembelian": "purchase", "dibeli": "purchase",
    "purchase": "purchase",
}

EDIT_PROMPT = """A shop owner is correcting a receipt that was parsed from a photo.
Items (numbered from 1):
{listing}
Total: {total}
Current type: {kind}
Owner message (casual Bahasa Indonesia, or English): "{text}"
Return JSON {{"edits": [...]}} where each edit is exactly one of:
{{"op":"set","index":int,"field":"name"|"qty"|"unit_price"|"subtotal","value":...}}
{{"op":"remove","index":int}}
{{"op":"add","name":str,"qty":number,"unit_price":integer}}
{{"op":"set_total","value":integer}}
{{"op":"set_type","value":"sale"|"purchase"|"unknown"}}
{{"op":"recalc_total"}}  (only when the owner asks to recalculate or recompute the total)
Amounts are Rupiah integers ("5rb" or "5k" = 5000). Ordinals like "yang kedua" or "ke-2" mean index 2.
Use set_type when the owner says the note is a sale (jual) or a purchase (beli) note.
If the message is not a correction, return {{"edits": []}}. Reply with JSON only."""


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def classify_reply(text):
    """Return 'confirm', 'reject' or None. Only whole yes/no answers count, so
    corrections like 'yang kedua 5 bukan 3' are never mistaken for a rejection."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words or any(w.isdigit() for w in words):
        return None
    ws = set(words)
    if ws <= (YES | NO):
        if ws & NO:
            return "reject"
        if ws & YES:
            return "confirm"
    return None


def direct_type(text):
    """A short message like 'jual', 'beli', 'nota beli', 'ya jual' sets the type."""
    toks = tokens(text)
    kinds = {TYPE_WORDS[t] for t in toks if t in TYPE_WORDS}
    if len(kinds) == 1 and len(toks) <= 3 and not toks & NO:
        return kinds.pop()
    return None


def interpret(data, text):
    listing = "\n".join(
        f"{k+1}. {i.get('name')}: qty {i.get('qty')}, unit_price {i.get('unit_price')}, subtotal {i.get('subtotal')}"
        for k, i in enumerate(data["items"]))
    r = client.chat.completions.create(
        model=MODEL, reasoning_effort="low",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": EDIT_PROMPT.format(
            listing=listing, total=data.get("total"), kind=data.get("type") or "unknown", text=text)}])
    return parse(r.choices[0].message.content).get("edits", [])


def apply_edits(data, edits):
    d = json.loads(json.dumps(data))
    d.pop("_total_change", None)
    before = validate(data)
    items = d["items"]
    removed, applied = set(), 0
    items_changed = manual_total = recalc = False
    for e in edits:
        try:
            op = e.get("op")
            if op == "set":
                k, f = e["index"] - 1, e["field"]
                if 0 <= k < len(items) and f in ("name", "qty", "unit_price", "subtotal"):
                    items[k][f] = e["value"] if f == "name" else float(e["value"]) if f == "qty" else int(e["value"])
                    items[k]["confidence"] = 1.0
                    if f in ("qty", "unit_price"):
                        items[k]["subtotal"] = round(items[k]["qty"] * items[k]["unit_price"])
                    applied += 1; items_changed = True
            elif op == "remove":
                removed.add(e["index"] - 1); applied += 1; items_changed = True
            elif op == "add":
                q, p = float(e["qty"]), int(e["unit_price"])
                items.append({"name": e["name"], "qty": q, "unit_price": p, "subtotal": round(q * p), "confidence": 1.0})
                applied += 1; items_changed = True
            elif op == "set_total":
                d["total"] = int(e["value"]); d["total_confidence"] = 1.0
                applied += 1; manual_total = True
            elif op == "set_type":
                kind = str(e.get("value") or "").lower()
                if kind in ("sale", "purchase", "unknown"):
                    d["type"] = kind; d["type_confidence"] = 1.0 if kind != "unknown" else 0.5
                    applied += 1
            elif op == "recalc_total":
                applied += 1; recalc = True
        except (KeyError, ValueError, TypeError):
            continue
    d["items"] = [i for k, i in enumerate(items) if k not in removed]
    if (recalc or (items_changed and before["total_ok"])) and not manual_total:
        new_sum = sum((i.get("subtotal") or 0) for i in d["items"])
        adj = sum((a.get("amount") or 0) for a in (d.get("adjustments") or []))
        pre_adj = adj == 0 or (before["total_ok"] and data.get("total") == before["items_sum"])
        d["total"] = new_sum if pre_adj else new_sum - adj
        d["total_confidence"] = 1.0
    if d.get("total") != data.get("total"):
        d["_total_change"] = [data.get("total"), d.get("total")]
    return d, applied


def handle_reply(data, text):
    kind = direct_type(text)
    if kind:
        d = json.loads(json.dumps(data))
        d["type"] = kind
        d["type_confidence"] = 1.0
        d.pop("_total_change", None)
        return "edited", d
    action = classify_reply(text)
    if action == "confirm":
        return "confirm", data
    if action == "reject":
        return "reject", data
    new, n = apply_edits(data, interpret(data, text))
    return ("edited", new) if n else ("unclear", data)


if __name__ == "__main__":
    from core import extract
    d, v, m = extract(sys.argv[1])
    while True:
        print("\n" + message(d, v) + "\n")
        reply = input("balasan> ")
        action, d2 = handle_reply(d, reply)
        if action == "confirm":
            d.pop("_total_change", None)
            print("\nTERSIMPAN (simulasi):"); print(json.dumps(d, indent=2, ensure_ascii=False)); break
        if action == "reject":
            print("Dibatalkan."); break
        if action == "unclear":
            d.pop("_total_change", None)
            print("\nSaya belum paham koreksinya. Contoh: 'yang kedua 5 bukan 3'."); continue
        d = d2; v = validate(d)
