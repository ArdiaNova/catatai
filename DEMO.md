# CatatAI — Demo Video Script

Target length: **2 min 30 s** · Format: 1080p, 30 fps, phone screen recording + voice-over
Language: **Bahasa Indonesia** narration, **English subtitles** on screen

---

## 0. Pre-flight (do this before opening the recorder)

- [ ] Delete the test transaction so `/ringkasan` starts clean.
      ```bash
      cd /home/nino/Documents/project/hackathon/celebral-valley
      ./demo_reset.sh
      ```
      Script ini otomatis memakai nomor pertama di `WHATSAPP_ALLOWED_NUMBERS`. Kalau mau nomor lain: `./demo_reset.sh 6285xxxx`.
- [ ] `https://catatai.ardianova.com/health` returns `{"ok":true}`.
- [ ] WhatsApp is logged in on the phone with the **demo number** (the owner number in `WHATSAPP_ALLOWED_NUMBERS`).
- [ ] The chat with **+62 851-5806-4660** is open and empty (or archive old messages).
- [ ] Turn on **Do Not Disturb**; hide notification banners and the status bar if possible.
- [ ] Set WhatsApp to a clean theme (light or dark, pick one and keep it).
- [ ] Real nota `images/gathan01.jpg` is in the phone gallery, cropped so only the nota is visible. Do **not** pre-blur it — blur in post.
- [ ] Screen recorder set to 1080p, microphone on.
- [ ] Screen mirroring/scrcpy is optional; recording on the phone is more reliable.

Timing note: extraction takes 10–25 s. Do not cut the wait; speed it up 2× in editing and label it `2× speed` on screen.

---

## 1. Cold open — title card (0:00–0:12)

**On screen:** dark background, white text.

```
CatatAI
WhatsApp back-office untuk UMKM Indonesia
Meta Global AI Developer Hackathon · Indie track
```

**Voice-over (ID):**
> "Pemilik warung mencatat penjualan di kertas. Setiap malam, kertasnya menumpuk dan tidak ada rekap."

**Subtitle (EN):**
> "Small shops record sales on paper. Every night the paper piles up — and there is no summary."

---

## 2. The problem, in one shot (0:12–0:25)

**On screen:** slow pan over 3–4 nota photos (use the synthetic eval photos; they are not customer data). Blur any names.

**Voice-over:**
> "Aplikasi pembukuan gagal karena minta input terstruktur. Padahal yang sudah mereka lakukan cuma: foto, kirim, chat."

**Subtitle:**
> "Bookkeeping apps fail because they demand structured input. What owners already do is: photograph, send, chat."

---

## 3. Greeting (0:25–0:40)

**Action:** open WhatsApp chat with **CatatAI (+62 851-5806-4660)**, send:

```
halo
```

**Bot reply (shown on screen):**

```
Halo! Saya CatatAI.
• Kirim foto nota, saya catat.
• Atau tulis transaksi, mis. 'jual es teh 10 gelas 5rb per gelas, beli gula 2 kilo 28rb total'.
• /summary untuk ringkasan hari ini.
• /lang en untuk English.
```

**Voice-over:**
> "Tidak ada aplikasi baru. Tidak ada form. Cukup chat seperti biasa."

**Subtitle:**
> "No new app. No forms. Just the chat they already use."

---

## 4. The core demo — real nota (0:40–1:35)

**Action:** send `images/gathan01.jpg` from the gallery. Keep the phone screen still while it uploads.

**Voice-over while waiting:**
> "Saya kirim foto nota laundry asli. Model membaca tanggal, jenis transaksi, item, jumlah, harga satuan, dan total."

**Bot reply (must match on screen):**

```
Dicatat 1 item, total Rp 60.000:
Jenis: penjualan (jual).
1. CUCI + SETRIKA: 10 Kg x Rp 6.000 = Rp 60.000

Benar?
Balas 'ya' jika benar, atau koreksi, misalnya 'yang kedua 5 bukan 3'.
```

**On-screen callouts (add in editing):**
- arrow at `Jenis: penjualan (jual)` → "inferred from the buyer line, not defaulted"
- arrow at `10 Kg x Rp 6.000` → "qty × unit price checked against subtotal"
- arrow at `Rp 60.000` → "total validated against item sum"

**Voice-over:**
> "Sebelum disimpan, bot membacakan hasilnya. Kalau ada yang salah, kita koreksi dengan bahasa biasa. Kalau benar, balas 'ya'."

**Subtitle:**
> "Before saving, it reads the result back. Correct it in plain language, or reply 'ya'."

---

## 5. Confirmation (1:35–1:50)

**Action:** send:

```
ya
```

**Bot reply:**

```
Tersimpan ✅ 1 item, total Rp 60.000.
```

**Voice-over:**
> "Satu pesan. Tersimpan ke database, lengkap dengan item dan tanggal nota."

**Subtitle:**
> "One message. Saved to the database with its line items and receipt date."

---

## 6. Daily summary (1:50–2:05)

**Action:** send:

```
/ringkasan
```

**Bot reply:**

```
Ringkasan 01-11-2026:
Penjualan: Rp 60.000
Pembelian: Rp 0
Estimasi untung (penjualan - pembelian): Rp 60.000
Terlaris: cuci + setrika (10)
```

**Voice-over:**
> "Dan langsung jadi ringkasan harian: penjualan, pembelian, estimasi untung, produk terlaris."

**Subtitle:**
> "And the day closes itself: sales, purchases, estimated profit, top sellers."

---

## 7. Proof it is real (2:05–2:20)

**On screen:** cut to a browser tab or Supabase table view showing the saved row and its items. Blur the owner id, phone number, and any customer name.

Show:
- `transactions`: type `sale`, `tx_date 2026-11-01`, `total 60000`
- `transaction_items`: `CUCI + SETRIKA`, qty `10`, unit `Kg`, unit_price `6000`, subtotal `60000`

**Voice-over:**
> "Ini bukan mockup. Barisnya benar-benar tersimpan di Supabase, dan bisa dibuka lagi kapan saja."

**Subtitle:**
> "This is not a mockup. The row is really in Supabase and can be queried later."

---

## 8. Evaluation + close (2:20–2:35)

**On screen:** results card.

```
15 nota · input tidak diubah
name / qty / subtotal   95.1%
unit_price              97.6%
total                   93.3%
jenis jual/beli        100.0%
latency rata-rata       21.4 s
```

**Voice-over:**
> "Di 15 nota uji, akurasi field 95,7 persen, jenis transaksi 100 persen. Yang ragu ditandai, bukan ditebak."

**Subtitle:**
> "On 15 test receipts: 95.7% field accuracy, 100% transaction-type accuracy. Uncertain lines are flagged, not guessed."

**Final card:**

```
CatatAI
catatai.ardianova.com
+62 851-5806-4660
```

---

## 9. Post-production

1. **Redact the customer name on the nota.** Blur or pixelate the name in **both** places it appears: the photo bubble in the WhatsApp chat and any full-screen preview. Keep the items and total readable. Do not blur the whole nota — judges need to see what the model read.
2. Blur the phone number/owner id in the database shot.
3. Add the English subtitles listed above. Keep them on screen at least 2 s.
4. Label the extraction wait `2× speed`.
5. Export H.264, 1080p, AAC audio, under 100 MB if the submission form has a size limit.
6. Upload unlisted to YouTube or directly to the submission form.
7. Put this in the video description:
   > "Demo uses a real laundry receipt. The customer name is redacted for privacy. The 15-receipt evaluation set is synthetic; evaluation inputs were not redacted."

---

## 10. Backup takes (only if the main take fails)

- **Correction take:** use a synthetic nota with 2+ items, send `yang kedua 5 bukan 3`, show the read-back change, then `ya`.
- **Purchase take:** use a synthetic nota with a supplier stamp (`AGEN ...`), show `Jenis: pembelian (beli)`.
- **Voice take:** send a voice note: `jual es teh 10 gelas lima ribu per gelas`, show the transcript + parsed entry.

Do not fake a pilot or a second user. If a take fails, re-record the same real flow.

---

## 11. Submission checklist

- [ ] Video uploaded and link works in incognito
- [ ] README pushed with the video link
- [ ] Eval numbers match `results/eval_report.md`
- [ ] Privacy policy live at `https://catatai.ardianova.com/privacy`
- [ ] App status **Live**
- [ ] Webhook returns 200 on a fresh inbound message
- [ ] No secrets, phone numbers, or customer names in the repo or video
- [ ] Submit before **Nov 5 2026, 09:00 WIB**
