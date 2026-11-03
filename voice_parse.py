import sys, json
from core import client, MODEL, parse, rp

PROMPT = """An Indonesian shop owner dictated this by voice (already transcribed): "__TEXT__"
Extract the entries into JSON:
{"entries":[{"type":"sale"|"purchase"|"unknown","name":str,"qty":number,"unit":str or null,"price_amount":integer or null,"price_basis":"per_unit"|"total"|"ambiguous"|"none","confidence":0.0-1.0}],"notes":str}
Rules:
- Convert number words to digits ("dua belas" = 12, "lima kilo" = qty 5, unit "kilo"). Rupiah amounts are integers ("5rb" or "lima ribu" = 5000).
- Never invent a price. Do not compute totals; only record the amount as stated.
- price_basis is "per_unit" only if the owner says per, tiap, @, satuan or similar. It is "total" only if the owner says semua, total, jadi, habis or similar.
- If a price follows a quantity without such a word, price_basis is "ambiguous" and confidence must be 0.5 or lower.
- If no price is mentioned, price_amount is null and price_basis is "none".
- "jual" or "laku" = sale. "beli", "kulakan", "belanja" = purchase. If there is no clue, type is "unknown" and confidence is below 0.6.
Reply with JSON only."""

def normalize(e):
    q, a, b = e.get("qty"), e.get("price_amount"), e.get("price_basis")
    e["unit_price"] = e["subtotal"] = None
    if a is not None and q:
        if b == "per_unit":
            e["unit_price"], e["subtotal"] = a, round(a * q)
        elif b == "total":
            e["subtotal"], e["unit_price"] = a, round(a / q)
    return e

def question(e):
    if e.get("type") == "unknown":
        return f"{e['name']}: dijual atau dibeli?"
    if e.get("price_basis") == "ambiguous" and e.get("price_amount") is not None:
        unit = e.get("unit") or "satuan"
        return f"{e['name']}: {rp(e['price_amount'])} itu per {unit} atau total untuk {e['qty']:g} {e.get('unit') or ''}?".strip()
    return None

def parse_voice(text):
    r = client.chat.completions.create(model=MODEL, reasoning_effort="low",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": PROMPT.replace("__TEXT__", text)}])
    d = parse(r.choices[0].message.content)
    d["entries"] = [normalize(e) for e in d.get("entries", [])]
    d["questions"] = [q for q in (question(e) for e in d["entries"]) if q]
    d["needs_confirmation"] = bool(d["questions"]) or any(
        (e.get("confidence") or 0) < 0.6 or e.get("type") == "unknown" for e in d["entries"])
    return d

if __name__ == "__main__":
    for text in sys.argv[1:]:
        print("IN :", text)
        print(json.dumps(parse_voice(text), indent=2, ensure_ascii=False), "\n")
