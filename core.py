import os, io, sys, json, time, base64
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps

load_dotenv()
client = OpenAI(api_key=os.environ["META_API_KEY"], base_url="https://api.meta.ai/v1")
MODEL = "muse-spark-1.3"
THRESHOLD = 0.6

PROMPT = """You are reading a photo of a handwritten or printed Indonesian shop receipt (nota) or ledger page.
Extract the data into JSON with exactly this shape:
{
  "is_nota": true,
  "date": "YYYY-MM-DD or null",
  "type": "sale" | "purchase" | "unknown",
  "type_confidence": 0.0-1.0,
  "items": [{"name": str, "qty": number, "unit": str or null, "unit_price": integer, "subtotal": integer, "confidence": 0.0-1.0}],
  "adjustments": [{"label": "dp" | "discount" | "other", "amount": integer}],
  "total": integer or null,
  "total_confidence": 0.0-1.0,
  "notes": "short remark about anything unclear"
}
Rules:
- Amounts are Indonesian Rupiah as plain integers. "87.500" or "87,500" means 87500. "5rb" or "5k" means 5000.
- Down payments (DP), discounts and similar lines go in adjustments, not in items.
- Never guess. If a field is hard to read, give it confidence below 0.6 and explain in notes.
- Keep item names in the original Indonesian wording.
- Put the unit as written on the nota (Kg, pcs, gelas, ikat, ...) in "unit"; use null when no unit is shown.
- If the image is not a receipt or ledger, set is_nota to false, items to [] and type to "unknown".

Transaction type: decide ONLY from a clue that is actually written on the paper.
- "sale": there is a buyer/customer line with an actual name, e.g. "Tuan Budi", "Kepada Ibu Sari", "Pelanggan ...", or the words "jual", "jualan", "penjualan", "terjual".
- A blank pre-printed label such as "Tuan/Toko: ......" is NOT a buyer clue. The name must be filled in.
- "purchase": there is a supplier mark, e.g. a stamp or header with "AGEN ...", "CV ...", "UD ...", "PASAR ...", "TOKO ...", or the words "beli", "pembelian", "dibeli".
- A bare shop name with no buyer line and no supplier stamp is not enough: use "unknown".
- NEVER default to "sale". If there is no explicit clue, set type to "unknown" and type_confidence below 0.6.
- type_confidence is your confidence in the type label itself, independent of the item confidences.
- Mention the clue you used in notes, e.g. "buyer line: Tuan Budi" or "supplier stamp: AGEN JAYA".
- Keep notes short, at most 20 words.
Reply with JSON only."""


def encode(image):
    src = io.BytesIO(image) if isinstance(image, bytes) else image
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def parse(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def normalize(d):
    """Indonesian notes often write the total in thousands: '80' means 80000.
    Only rescale when the line items confirm the missing factor of 1000."""
    items = d.get("items") or []
    items_sum = sum((i.get("subtotal") or 0) for i in items)
    total = d.get("total")
    if isinstance(total, (int, float)) and 0 < total < 1000 and items_sum >= 1000:
        if abs(items_sum - total * 1000) <= max(1, 0.01 * items_sum):
            d["total"] = int(round(total * 1000))
    return d


def call_model(image, effort):
    r = client.chat.completions.create(
        model=MODEL,
        reasoning_effort=effort,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encode(image)}},
        ]}],
    )
    u = getattr(r, "usage", None)
    toks = (getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0)
    return normalize(parse(r.choices[0].message.content)), toks


def rotate(image, angle):
    """Rotate after downscaling so this stays cheap even for large photos."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(image))).convert("RGB")
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.rotate(angle, expand=True).save(buf, "JPEG", quality=90)
    return buf.getvalue()


def is_landscape(image):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(image)))
    return im.width > im.height


def validate(d):
    items = d.get("items") or []
    items_sum = sum((i.get("subtotal") or 0) for i in items)
    adj = sum((a.get("amount") or 0) for a in (d.get("adjustments") or []))
    total = d.get("total")
    # Total on a nota may be before or after DP/discount, so accept either.
    total_ok = total is not None and total in (items_sum, items_sum - adj)
    low = set()
    for k, i in enumerate(items):
        if (i.get("confidence") or 0) < THRESHOLD:
            low.add(k)
        q, p, s = i.get("qty"), i.get("unit_price"), i.get("subtotal")
        if all(isinstance(x, (int, float)) for x in (q, p, s)) and abs(q * p - s) > max(1, 0.01 * s):
            low.add(k)
    total_low = (d.get("total_confidence") or 0) < THRESHOLD
    kind = str(d.get("type") or "unknown").strip().lower()
    if kind not in ("sale", "purchase"):
        kind = "unknown"
    d["type"] = kind
    tconf = d.get("type_confidence")
    type_low = kind == "unknown" or not isinstance(tconf, (int, float)) or tconf < THRESHOLD
    return {"items_sum": items_sum, "adjustments_sum": adj, "total_ok": total_ok,
            "low_items": sorted(low), "total_low": total_low,
            "type_low": type_low,
            "needs_confirmation": bool(low) or total_low or not total_ok or type_low}


def score(d, v):
    """Higher is better. Used to pick between the original and rotated reads."""
    if not d or not d.get("is_nota", True) or not (d.get("items")):
        return -1.0
    s = 3.0 if v["total_ok"] else 0.0
    s += 1.0 if d.get("type") in ("sale", "purchase") else 0.0
    s += float(d.get("type_confidence") or 0) * 0.5
    confs = [float(i.get("confidence") or 0) for i in d["items"]]
    s += sum(confs) / len(confs) if confs else 0.0
    for i in d["items"]:
        q, p, st = i.get("qty"), i.get("unit_price"), i.get("subtotal")
        if all(isinstance(x, (int, float)) for x in (q, p, st)) and abs(q * p - st) > max(1, 0.01 * st):
            s -= 0.5
    return s


def extract(image, effort="medium", try_rotation=True):
    t = time.time()
    tin = tout = 0
    best = (-2.0, None, None)
    rotated = False

    for _ in range(2):  # retry once on bad JSON or mismatched total
        try:
            data, (a, b) = call_model(image, effort)
            tin += a; tout += b
        except Exception:
            continue
        v = validate(data)
        sc = score(data, v)
        if sc > best[0]:
            best = (sc, data, v)
        if not data.get("is_nota", True) or v["total_ok"]:
            break

    _, data, v = best
    # Landscape photos are often taken sideways. If the first read is shaky,
    # try both rotations and keep whichever read scores best.
    if try_rotation and v and v["needs_confirmation"] and is_landscape(image):
        for angle in (90, 270):
            try:
                d2, (a, b) = call_model(rotate(image, angle), "low")
                tin += a; tout += b
            except Exception:
                continue
            v2 = validate(d2)
            sc2 = score(d2, v2)
            if sc2 > best[0] + 0.15:
                best = (sc2, d2, v2)
                rotated = True
        _, data, v = best

    meta = {"latency_s": round(time.time() - t, 1), "tokens_in": tin, "tokens_out": tout,
            "effort": effort, "rotated": rotated}
    return data, v, meta


def rp(n):
    return "Rp " + f"{int(n):,}".replace(",", ".") if n is not None else "?"


def message(d, v, lang="id"):
    T = {
        "id": {"bad": "Maaf, saya tidak bisa membaca nota dari foto ini. Coba foto ulang dengan cahaya lebih terang.",
               "head": "Dicatat {n} item, total {t}:", "mis": "⚠️ Total di nota ({t}) tidak sama dengan jumlah item ({s}).",
               "tot": "⚠️ Total belum jelas terbaca.",
               "sale": "Jenis: penjualan (jual).", "purchase": "Jenis: pembelian (beli).",
               "unknown": "Jenis: belum jelas, ini nota jual atau beli?",
               "ask_type": "Balas 'jual' atau 'beli' untuk memperbaiki jenisnya.",
               "ok": "Benar?", "chk": "Baris bertanda ⚠️ perlu dicek.",
               "ask": "Balas 'ya' jika benar, atau koreksi, misalnya 'yang kedua 5 bukan 3'."},
        "en": {"bad": "Sorry, I can't read a receipt in this photo. Please retake it in brighter light.",
               "head": "Logged {n} items, total {t}:", "mis": "⚠️ The total on the receipt ({t}) doesn't match the sum of items ({s}).",
               "tot": "⚠️ The total is hard to read.",
               "sale": "Type: sale.", "purchase": "Type: purchase.",
               "unknown": "Type: unclear, is this a sale or a purchase note?",
               "ask_type": "Reply 'sale' or 'purchase' to fix the type.",
               "ok": "Correct?", "chk": "Lines marked ⚠️ need checking.",
               "ask": "Reply 'yes' if correct, or correct me, e.g. 'the second one is 5, not 3'."},
    }[lang]
    if d is None or not d.get("is_nota", True) or not d.get("items"):
        return T["bad"]
    items = d["items"]
    out = [T["head"].format(n=len(items), t=rp(d.get("total")))]
    out.append(T.get(d.get("type"), T["unknown"]))
    for k, i in enumerate(items):
        mark = " ⚠️" if k in v["low_items"] else ""
        qty = f"{i.get('qty')} {i.get('unit')}".strip() if i.get("unit") else i.get("qty")
        out.append(f"{k+1}. {i.get('name')}: {qty} x {rp(i.get('unit_price'))} = {rp(i.get('subtotal'))}{mark}")
    ch = d.get("_total_change")
    if ch:
        out.append(("ℹ️ Total berubah: " if lang == "id" else "ℹ️ Total changed: ") + f"{rp(ch[0])} → {rp(ch[1])}")
    if d.get("total") is None:
        out.append(T["tot"])
    elif not v["total_ok"]:
        out.append(T["mis"].format(t=rp(d.get("total")), s=rp(v["items_sum"])))
    if v["type_low"]:
        out.append(T["ask_type"])
    if v["low_items"]:
        out.append(T["chk"])
    out.append(T["ok"] if not v["needs_confirmation"] else "")
    out.append(T["ask"])
    return "\n".join(x for x in out if x)


if __name__ == "__main__":
    lang = os.environ.get("REPLY_LANG", "id")
    for p in sys.argv[1:]:
        d, v, m = extract(p)
        print(f"=== {p} | {m}")
        print(message(d, v, lang))
        print(f"needs_confirmation={v['needs_confirmation'] if v else None}\n")
