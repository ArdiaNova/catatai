# PRD: CatatAI – WhatsApp Back-Office Agent for Indonesian SMEs

Meta Global AI Developer Hackathon · Indie Developer track · Theme: Build for Your World

Owner: Nino Ardianto (ArdiaNova) · Status: Draft v1 · Build window: Oct 28 – Nov 4, 2026 (submission due Nov 4, 9:00 PM ET = Nov 5, 09:00 WIB)

CatatAI is a working title.

## 1. Summary

CatatAI is a WhatsApp-native back-office agent for small shop owners in Indonesia (warung, toko, kedai). Owners keep their business in handwritten notes and chat messages and rarely use bookkeeping apps, because typing structured data is too much friction. CatatAI works with what they already do: they send a photo, a voice note, or a short message in Bahasa Indonesia, and the agent turns it into clean records, stock counts, and a daily summary.

The product is built on Meta’s models through the Meta Model API: Muse Spark for multimodal understanding and agent reasoning, SAM 3.1 for segmentation and counting, Muse Image for catalog visuals, and the Audio endpoint for voice notes (to be verified).

## 2. Problem

- Millions of small Indonesian merchants record sales and purchases on paper notas, ledgers, or not at all.
- Existing bookkeeping and POS apps need typing, setup, and habit change. Most owners abandon them.
- Owners already live in WhatsApp all day. Photos and voice notes are their natural input.
- Result: no clear view of daily revenue, margins, or what to restock, and poor-quality product photos for selling online.

## 3. Target users

Primary: owner-operators of warung, toko kelontong, kedai kopi, and small food stalls, aged 25–55, comfortable with WhatsApp but not with accounting software. Language: Bahasa Indonesia, casual, with regional abbreviations.

Secondary: small online sellers who need quick product images and catalog text.

Persona: Ibu Sari runs a toko kelontong. She writes sales and purchases on a notebook page every evening and wants to know whether she made money this week and what to buy tomorrow.

## 4. Goals and non-goals

### Goals

1. Turn a photo of a handwritten nota or ledger page into structured transactions with high field-level accuracy.
2. Let owners log transactions by voice note or short Bahasa message.
3. Count stock from a shelf photo and flag low items.
4. Generate a plain-Bahasa daily summary (revenue, expenses, top sellers, restock suggestions).
5. Generate a clean catalog image from a phone snapshot of a product.
6. Ship a reliable, demoable end-to-end WhatsApp flow within the hackathon window.

### Non-goals (for the hackathon)

- Payments, tax reporting, or integration with accounting software.
- Multi-user roles or multi-store management.
- A full web dashboard (a minimal read-only view is optional).
- Supporting languages other than Bahasa Indonesia (English replies are a bonus).

## 5. Success metrics

- Nota extraction: at least 85% field-level accuracy (item, quantity, price, total) on the labeled test set, measured before and after the confirmation loop.
- Time to log a transaction: under 20 seconds from photo or voice note to confirmed record.
- Shelf counting: within ±1 item on at least 80% of products in the test photos.
- Pilot: at least 2 real shop owners use it on real data during the build window, with a before/after time-saved estimate.
- Demo: a recorded end-to-end flow under 3 minutes that works live.

## 6. Scope

### Must have (MVP)

- WhatsApp webhook receiving text, image, and audio messages and replying in Bahasa.
- Nota/ledger photo → structured JSON → confirmation message → saved transactions.
- Confidence scoring with a one-tap confirm/correct reply for uncertain fields.
- Transaction store with daily totals.
- Daily summary message.
- Small labeled evaluation set and an accuracy report.

### Should have

- Voice note → transaction logging.
- Shelf photo → item counts and low-stock alert (SAM 3.1).

### Could have (stretch)

- Product snapshot → clean catalog image and short product description (Muse Image).
- Weekly summary and simple restock suggestions.
- Minimal read-only web view of the ledger.

## 7. User flows

### Flow A: Log a nota by photo

1. Owner sends a photo of a handwritten nota.
2. Agent extracts line items, quantities, prices, and total into a fixed JSON schema.
3. Agent replies with a short readable summary: “Dicatat 3 item, total Rp 87.500. Benar?” with confirm and edit options.
4. Fields below the confidence threshold are listed explicitly for the owner to correct.
5. On confirmation, transactions are saved.

### Flow B: Log by voice or text

1. Owner sends a voice note, for example “tadi jual 12 kopi susu, beli susu 3 liter”.
2. Audio is transcribed, parsed into sale and purchase entries, and confirmed the same way as Flow A.

### Flow C: Count stock from a shelf photo

1. Owner sends a shelf or stockroom photo.
2. SAM 3.1 segments items; Muse Spark labels product types and counts them.
3. Agent compares with the previous count and replies with low-stock items.

### Flow D: Catalog image

1. Owner sends a phone snapshot of a product.
2. Muse Image returns a cleaned product image on a plain background; Muse Spark writes a short Bahasa caption.

### Flow E: Daily summary

Every evening the agent sends a summary: revenue, expenses, estimated profit, top sellers, and one or two restock suggestions, in plain Bahasa.

## 8. Functional requirements

- FR1: Accept WhatsApp messages (text, image, audio) via webhook and respond within 15 seconds for photo flows.
- FR2: Extract nota content into a strict JSON schema: date, items\[name, qty, unit\_price, subtotal\], total, type (sale or purchase).
- FR3: Attach a confidence value to each extracted field. Any field below the threshold must be confirmed by the owner before saving.
- FR4: Never save low-confidence data silently.
- FR5: Allow corrections by plain reply, for example “yang kedua 5 bukan 3”.
- FR6: Persist transactions per owner (phone number as identifier).
- FR7: Produce the daily summary from stored transactions.
- FR8: Shelf counting returns a count per product type and a delta against the previous count.
- FR9: All replies are in clear, standard Bahasa Indonesia, short, and free of jargon.
- FR10: Log every model call (input type, latency, token usage) to track cost and performance.

## 9. Technical design

### Architecture

- Channel: WhatsApp Business Cloud API webhook (existing setup can be reused).
- Backend: a small TypeScript or Python service (Next.js API routes or FastAPI) that routes each message to a flow handler.
- Storage: Supabase (Postgres) for owners, transactions, stock counts, and logs; Supabase storage for images.
- Models via Meta Model API:
  - Muse Spark: nota understanding, voice-text parsing, summaries, Bahasa replies, agent routing.
  - SAM 3.1: item segmentation for shelf photos.
  - Muse Image: catalog image generation.
  - Audio endpoint: voice note transcription (verify availability and Bahasa quality; fallback is an open-weight ASR model on Modal or Baseten).

### Agent loop

1. Classify the incoming message (nota photo, shelf photo, product photo, voice, text question).
2. Call the matching flow with a structured-output prompt and schema validation.
3. Validate the output (totals add up, numbers plausible). If validation fails, retry once, then ask the owner.
4. Reply, wait for confirmation, then persist.

### Reliability features (technical depth)

- Arithmetic cross-check: line items must sum to the total; mismatches lower confidence.
- Confirmation loop for uncertain fields.
- Idempotent webhook handling to avoid duplicate records from retries.
- Fallback messages when a model call fails or times out.

### Data model (simplified)

- owners(id, phone, shop\_name, created\_at)
- transactions(id, owner\_id, type, date, total, source\[photo|voice|text\], confirmed\_at)
- transaction\_items(id, transaction\_id, name, qty, unit\_price, subtotal, confidence)
- stock\_counts(id, owner\_id, product, count, counted\_at, image\_url)
- model\_calls(id, flow, model, latency\_ms, tokens\_in, tokens\_out, created\_at)

## 10. Evaluation plan

- Collect 15–30 real handwritten notas or ledger pages from small shops, with owner permission and sensitive details blurred, plus 5–10 shelf photos. Hand-label the ground truth.
- Measure field-level accuracy (item name, quantity, price, total) and report it before and after the confirmation loop.
- Measure shelf-count error against manual counts.
- Report latency and cost per flow from the model\_calls log.
- Include the results table in the submission write-up and the demo.

## 11. Demo plan (25% of the score)

Target length: under 3 minutes, recorded from a real phone using the real WhatsApp number.

1. 0:00–0:20: the problem. A real shop, a real handwritten nota.
2. 0:20–1:10: send the nota photo, see the structured confirmation, correct one field, confirm.
3. 1:10–1:40: send a voice note in Bahasa, see it logged.
4. 1:40–2:10: shelf photo, see counts and a low-stock alert.
5. 2:10–2:30: daily summary message.
6. 2:30–2:50: catalog image (if built) and the accuracy results.
7. 2:50–3:00: closing line on impact for Indonesian SMEs.

Record a backup video in case the live demo has issues.

## 12. How this maps to the judging criteria

- Impact (30%): a real problem for a very large underserved market, tested with real shop owners, with measured time saved.
- Use of Meta AI tooling (25%): several Meta models in one coherent product (Muse Spark, SAM 3.1, Muse Image, Audio), going beyond a single basic integration.
- Demo (25%): an end-to-end WhatsApp flow on a real phone, with a polished video.
- Technical depth and execution (20%): schema-validated extraction, confidence scoring, arithmetic checks, a confirmation loop, and a published evaluation.

## 13. Timeline

- Oct 28: confirm API access, billing, and credits. Run Muse Spark on the first sample notas. Set up the WhatsApp webhook and database.
- Oct 29: nota photo flow with JSON schema, confidence scores, and the confirmation loop.
- Oct 30: transaction storage and the daily summary.
- Oct 31: voice note flow.
- Nov 1: shelf counting with SAM 3.1.
- Nov 2: pilot with 2–3 shop owners. Run the evaluation. Catalog image flow if time allows.
- Nov 3: bug fixes, polish, record the demo video, write the submission text.
- Nov 4 (morning WIB): submit with a buffer before the deadline of Nov 5, 09:00 WIB.

The $150 in credits may take up to 2 business days to appear, so avoid heavy testing before they arrive.

## 14. Risks and mitigations

- Credits arrive late: use a small, low-limit card with a spend alert and keep early tests light.
- Handwriting accuracy is weaker than expected: narrow the scope to printed or neat notas, rely on the confirmation loop, and report honest numbers.
- Bahasa voice transcription is weak: use an open-weight ASR fallback, or make voice a stretch feature.
- WhatsApp setup problems or number restrictions: keep a simple fallback channel such as a web chat or Telegram bot so the demo still works.
- Scope creep: freeze the MVP (Flow A, summary, evaluation) first, then add features one at a time.
- Privacy of shop photos: get owner permission, blur sensitive details, and store only what is needed.

## 15. Open questions to verify

- Exact model names and endpoints available in the Meta Model API (the waiver and the event page use slightly different names).
- Whether the Audio endpoint supports Bahasa Indonesia transcription well enough.
- Rate limits and per-call cost for image inputs.
- Whether pre-existing code (such as the existing WhatsApp webhook setup) is allowed under the official rules, which are published before the event.
