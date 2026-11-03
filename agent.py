import time
from core import extract, message, validate, rp
from corrections import handle_reply, classify_reply
from voice_parse import parse_voice
import store
import entry_edits
import voice

STR = {
    "id": {
        "welcome": "Halo! Saya CatatAI.\n• Kirim foto nota, saya catat.\n• Atau tulis transaksi, mis. 'jual es teh 10 gelas 5rb per gelas, beli gula 2 kilo 28rb total'.\n• /summary untuk ringkasan hari ini.\n• /lang en untuk English.",
        "saved_nota": "Tersimpan ✅ {n} item, total {t}.", "saved_voice": "Tersimpan ✅ {n} item.",
        "cancelled": "Dibatalkan.", "unclear": "Saya belum paham koreksinya. Contoh: 'yang kedua 5 bukan 3'.",
        "voice_off": "Voice note belum didukung. Kirim teks atau foto nota dulu.",
        "nohelp": "Saya tidak menemukan transaksi di pesan itu. Contoh: 'jual kopi susu 12 gelas'.",
        "voice_head": "Dicatat {n} entri:", "voice_ask": "Balas 'ya' jika benar, atau tambahkan keterangan.",
        "sale": "jual", "purchase": "beli", "lang_ok": "Bahasa balasan: Indonesia.", "lang_usage": "Gunakan /lang id atau /lang en.",
    },
    "en": {
        "welcome": "Hi! I'm CatatAI.\n• Send a photo of a receipt and I'll log it.\n• Or type transactions, e.g. 'sold iced tea 10 glasses 5k each, bought sugar 2 kilo 28k total'.\n• /summary for today's summary.\n• /lang id for Bahasa Indonesia.",
        "saved_nota": "Saved ✅ {n} items, total {t}.", "saved_voice": "Saved ✅ {n} items.",
        "cancelled": "Cancelled.", "unclear": "I didn't understand the correction. Example: 'the second one is 5, not 3'.",
        "voice_off": "Voice notes aren't supported yet. Please send text or a receipt photo.",
        "nohelp": "I couldn't find a transaction in that message. Example: 'sold 12 milk coffees'.",
        "voice_head": "Logged {n} entries:", "voice_ask": "Reply 'yes' if correct, or add details.",
        "sale": "sale", "purchase": "purchase", "lang_ok": "Reply language: English.", "lang_usage": "Use /lang id or /lang en.",
    },
}

def voice_message(d, lang):
    S = STR[lang]
    out = [S["voice_head"].format(n=len(d["entries"]))]
    tag = {"sale": S["sale"], "purchase": S["purchase"], "unknown": "?"}
    for k, e in enumerate(d["entries"], 1):
        qv = e.get("qty")
        qty = f"{qv:g}" if isinstance(qv, (int, float)) else "?"
        line = f"{k}. [{tag.get(e.get('type'), '?')}] {e.get('name')}: {qty} {e.get('unit') or ''}".rstrip()
        if e.get("unit_price") is not None:
            line += f" x {rp(e['unit_price'])}"
        if e.get("subtotal") is not None:
            line += f" = {rp(e['subtotal'])}"
        if (e.get("confidence") or 0) < 0.6 or e.get("type") == "unknown":
            line += " ⚠️"
        out.append(line)
    out += ["❓ " + x for x in d.get("questions", [])]
    out.append(S["voice_ask"])
    return "\n".join(out)

def _photo(oid, lang, image):
    d, v, meta = extract(image)
    store.log_call(oid, "nota_photo", meta, ok=bool(d))
    msg = message(d, v, lang)
    if d and d.get("is_nota", True) and d.get("items"):
        store.save_pending(oid, "nota", "photo", {"data": d, "original": d})
    return msg

def _reply_pending(oid, lang, p, text):
    S = STR[lang]
    payload = p["payload"]
    if p["kind"] == "nota":
        data, original = payload["data"], payload["original"]
        action, d2 = handle_reply(data, text)
        if action == "confirm":
            store.save_nota(oid, data, original)
            store.clear_pending(oid)
            return S["saved_nota"].format(n=len(data["items"]), t=rp(data.get("total")))
        if action == "reject":
            store.clear_pending(oid)
            return S["cancelled"]
        if action == "unclear":
            return S["unclear"]
        msg = message(d2, validate(d2), lang)
        d2.pop("_total_change", None)
        store.save_pending(oid, "nota", "photo", {"data": d2, "original": original})
        return msg
    # typed transaction log
    action = classify_reply(text)
    if action == "confirm":
        entries = payload["parsed"]["entries"]
        store.save_voice(oid, entries, payload["original"], edited=payload.get("rounds", 0) > 0, source=p["source"])
        store.clear_pending(oid)
        return S["saved_voice"].format(n=len(entries))
    if action == "reject":
        store.clear_pending(oid)
        return S["cancelled"]
    new, n = entry_edits.apply(payload["parsed"], text)
    if not n:
        return S["unclear"]
    store.save_pending(oid, "voice", p["source"], {"text": payload["text"], "original": payload["original"],
                                                 "parsed": new, "rounds": payload.get("rounds", 0) + 1})
    return voice_message(new, lang)

def _new_text(oid, lang, text):
    t0 = time.time()
    d = parse_voice(text)
    store.log_call(oid, "text_parse", {"latency_s": time.time() - t0})
    if not d["entries"]:
        return STR[lang]["nohelp"]
    store.save_pending(oid, "voice", "text", {"text": text, "original": {"text": text, "entries": d["entries"]},
                                              "parsed": d, "rounds": 0})
    return voice_message(d, lang)

def handle(channel, ext_id, message_id, kind, text=None, image=None, audio=None):
    """Returns the reply text, or None if this message was already processed."""
    if message_id and not store.mark_processed(f"{channel}:{message_id}"):
        return None
    owner = store.get_owner(channel, ext_id)
    oid, lang = owner["id"], owner["language"]
    S = STR[lang]
    if kind == "voice":
        return _voice(oid, lang, audio)
    if kind == "photo":
        return _photo(oid, lang, image)
    t = (text or "").strip()
    low = t.lower()
    if low.startswith("/start") or low.startswith("/help"):
        return S["welcome"]
    if low.startswith("/lang"):
        parts = low.split()
        if len(parts) > 1 and parts[1] in ("id", "en"):
            store.set_language(oid, parts[1])
            return STR[parts[1]]["lang_ok"]
        return S["lang_usage"]
    if low in ("/summary", "/ringkasan", "summary", "ringkasan"):
        return store.summary_text(store.summary_data(oid), lang)
    if low.strip(" .!,") in ("halo", "hai", "hi", "hello", "pagi", "siang", "malam",
                              "assalamualaikum", "salam", "mulai", "start"):
        return S["welcome"]
    pending = store.load_pending(oid)
    if pending:
        return _reply_pending(oid, lang, pending, t)
    return _new_text(oid, lang, t)

VSTR = {
    "id": {"heard": "Saya dengar: \u201c{t}\u201d",
           "empty": "Suara belum terdengar jelas. Coba rekam ulang lebih dekat ke mikrofon.",
           "fail": "Maaf, voice note belum bisa diproses sekarang. Coba kirim teks dulu."},
    "en": {"heard": "I heard: \u201c{t}\u201d",
           "empty": "I couldn't hear that clearly. Please record again, closer to the microphone.",
           "fail": "Sorry, I can't process voice notes right now. Please send text for now."},
}

def _voice(oid, lang, audio):
    V = VSTR[lang]
    if not audio:
        return STR[lang]["voice_off"]
    t0 = time.time()
    try:
        text = voice.transcribe(audio)
    except Exception as e:
        store.log_call(oid, "voice_transcribe", {"latency_s": time.time() - t0}, ok=False)
        print("voice error:", type(e).__name__, str(e)[:200])
        return V["fail"]
    store.log_call(oid, "voice_transcribe", {"latency_s": time.time() - t0})
    if not text:
        return V["empty"]
    heard = V["heard"].format(t=text)
    pending = store.load_pending(oid)
    if pending:
        return heard + "\n" + _reply_pending(oid, lang, pending, text)
    d = parse_voice(text)
    if not d["entries"]:
        return heard + "\n" + STR[lang]["nohelp"]
    store.save_pending(oid, "voice", "voice", {"text": text, "original": {"transcript": text, "entries": d["entries"]},
                                               "parsed": d, "rounds": 0})
    return heard + "\n" + voice_message(d, lang)
