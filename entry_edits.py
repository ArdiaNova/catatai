import json
from core import client, MODEL, parse
from voice_parse import normalize, question

PROMPT = """An Indonesian shop owner is correcting a list of logged entries. Voice transcripts can contain mishearings (for example "ekstrak" instead of "es teh").
Entries (numbered from 1):
__LISTING__
Open questions:
__QUESTIONS__
Owner message: "__TEXT__"
Return JSON {"edits": [...]} where each edit is exactly one of:
{"op":"set","index":int,"field":"type"|"name"|"qty"|"unit"|"price_amount"|"price_basis","value":...}
{"op":"remove","index":int}
{"op":"add","type":"sale"|"purchase"|"unknown","name":str,"qty":number,"unit":str or null,"price_amount":integer or null,"price_basis":"per_unit"|"total"|"ambiguous"|"none"}
Rules:
- type is exactly "sale", "purchase" or "unknown". price_basis is exactly "per_unit", "total", "ambiguous" or "none".
- An answer such as "per gelas" or "per kilo" to an open question sets price_basis "per_unit" on that entry. "total" or "semua" sets "total".
- "X adalah jual" or "X dijual" sets type "sale" on the entry named X. "dibeli" or "beli" sets "purchase".
- If the owner replaces a misheard name ("bukan ekstrak, es teh"), set the name of that entry.
- If the message describes a new transaction that is not in the list, use "add".
- Do not change fields the owner did not mention. If the message is not a correction or addition, return {"edits": []}.
Reply with JSON only."""

FIELDS = {"type", "name", "qty", "unit", "price_amount", "price_basis"}
TYPES = {"sale", "purchase", "unknown"}
BASES = {"per_unit", "total", "ambiguous", "none"}
ALIAS = {"jual": "sale", "dijual": "sale", "beli": "purchase", "dibeli": "purchase"}

def interpret(parsed, text):
    listing = "\n".join(
        f"{k+1}. type={e.get('type')} name={e.get('name')} qty={e.get('qty')} unit={e.get('unit')} "
        f"price_amount={e.get('price_amount')} price_basis={e.get('price_basis')}"
        for k, e in enumerate(parsed["entries"]))
    qs = "\n".join(parsed.get("questions", [])) or "(none)"
    prompt = PROMPT.replace("__LISTING__", listing).replace("__QUESTIONS__", qs).replace("__TEXT__", text)
    r = client.chat.completions.create(model=MODEL, reasoning_effort="low",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}])
    return parse(r.choices[0].message.content).get("edits", [])

def apply(parsed, text):
    d = json.loads(json.dumps(parsed))
    entries = d["entries"]
    removed, n = set(), 0
    for e in interpret(parsed, text):
        try:
            op = e.get("op")
            if op == "set":
                k, f, v = e["index"] - 1, e["field"], e["value"]
                if not (0 <= k < len(entries)) or f not in FIELDS:
                    continue
                if f == "type":
                    v = ALIAS.get(v, v)
                    if v not in TYPES:
                        continue
                elif f == "price_basis":
                    if v not in BASES:
                        continue
                elif f == "qty":
                    v = float(v)
                elif f == "price_amount":
                    v = None if v is None else int(v)
                entries[k][f] = v
                entries[k]["confidence"] = 1.0
                if f == "price_amount" and entries[k].get("price_basis") in (None, "none") and v is not None:
                    entries[k]["price_basis"] = "ambiguous"
                n += 1
            elif op == "remove":
                removed.add(e["index"] - 1)
                n += 1
            elif op == "add":
                amt = e.get("price_amount")
                entries.append({
                    "type": ALIAS.get(e.get("type"), e.get("type")) if ALIAS.get(e.get("type"), e.get("type")) in TYPES else "unknown",
                    "name": e["name"], "qty": float(e.get("qty") or 1), "unit": e.get("unit"),
                    "price_amount": amt,
                    "price_basis": e.get("price_basis") if e.get("price_basis") in BASES else ("none" if amt is None else "ambiguous"),
                    "confidence": 0.9})
                n += 1
        except (KeyError, ValueError, TypeError):
            continue
    d["entries"] = [normalize(x) for k, x in enumerate(entries) if k not in removed]
    d["questions"] = [q for q in (question(x) for x in d["entries"]) if q]
    d["needs_confirmation"] = bool(d["questions"]) or any(
        (x.get("confidence") or 0) < 0.6 or x.get("type") == "unknown" for x in d["entries"])
    return d, n
