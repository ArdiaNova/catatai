# Submission copy

Copy-paste fields for the Meta Global AI Developer Hackathon form. Adjust the video link once uploaded.

---

## Project name

CatatAI

## Tagline (one line)

A WhatsApp back-office that turns photos, voice notes, and plain Indonesian into clean sales records.

## Short description (under 300 characters)

CatatAI lets Indonesian shop owners send a photo of a handwritten nota on WhatsApp and get a structured sales or purchase record back. It reads the receipt, asks for confirmation in plain language, then saves items, quantities, prices, and totals to a database.

## Long description

Small shops in Indonesia still run on paper. A laundry writes each order on a nota, hands the copy to the customer, and keeps the carbon. At the end of the day there is no reliable total, no stock count, and no profit figure.

Bookkeeping apps have not fixed this because they require structured input: choose a date, choose a category, type every line, save. That is more work than the paper, so owners stop after a week.

CatatAI removes the form. The owner opens WhatsApp — the app already on their phone — and sends a photo, a voice note, or one sentence. CatatAI reads it with Meta's multimodal model, shows the parsed items and total, and asks "Benar?" before saving. Corrections happen in normal language: "yang kedua 5 bukan 3". Confirmation is one word: "ya". `/ringkasan` returns today's sales, purchases, estimated profit, and top sellers, falling back to the latest day with data when today is empty.

The agent is deliberately careful. It verifies WhatsApp webhook signatures, makes message handling idempotent, expires pending confirmations after an hour, flags low-confidence lines instead of guessing, checks quantity × unit price against each subtotal, and refuses to default an ambiguous nota to "sale".

WhatsApp is the primary channel. A Telegram fallback runs the same agent pipeline and the same database, so a record started there is visible from WhatsApp.

## How it uses Meta AI models

- **`muse-spark-1.3`** reads nota photos and returns structured JSON: date, sale/purchase type, items, quantity, unit, unit price, subtotal, total, confidence. It also parses typed and transcribed transactions.
- **`muse-voice-transcribe-1.0`** transcribes WhatsApp voice notes in Bahasa Indonesia before parsing.
- **`sam-3.1`** and **`muse-image-1.0`** are scoped in the PRD for product segmentation and catalog visuals. They are roadmap items, not part of the demoed nota flow.

The WhatsApp integration uses the Cloud API with a system-user token, app-level webhook subscription, and signature verification.

## Channels

- **WhatsApp Cloud API** — primary channel, used in the demo. Webhook with signature verification, media download, and free-form replies inside the 24-hour window.
- **Telegram Bot API** — fallback channel via long polling. Same `agent.handle` pipeline, same Supabase tables, same allowlist model. Supports text, photos, and voice notes. Runs as a separate process, not inside the production container.

## What was hard

- **Sale vs purchase.** Early versions defaulted every legible nota to "sale". That is wrong for supplier notes and dangerous for bookkeeping. The fix was to require an explicit clue — a filled-in buyer line, or a supplier stamp/header — and otherwise ask the user. Type accuracy on the eval set is now 100%.
- **Indonesian number formats.** "87.500", "87,500", and "5rb" all mean different things to a parser. Totals written in thousands ("80" meaning 80,000) are only rescaled when the line items confirm the factor.
- **Sideways photos.** A landscape photo is often a portrait nota rotated. The agent retries at 90° and 270° only when the first read fails validation, which keeps cost down.
- **Trust.** A back-office tool that silently saves a wrong total is worse than paper. Every save goes through a read-back and an explicit confirmation, and mismatched totals are surfaced, not corrected.

## Evaluation

15 Indonesian nota photos, ground truth written by hand, inputs unmodified.

- Field accuracy: **95.7%**
- Total accuracy: **93.3%**
- Sale/purchase type: **100%**
- Item count: **100%**
- Average latency: **21.4 s** per nota
- Cost for the full run: **$0.2561**

The eval photos are synthetic nota created for testing. The one real receipt used in the demo is private and not published. Demo redaction is disclosed in the README and video description.

## Challenges / limitations

- Free-form WhatsApp replies only work inside the 24-hour customer service window.
- One pending record per owner keeps state simple but requires two confirmations for two back-to-back receipts.
- Handwriting quality still matters; low-confidence lines are flagged.
- `003.jpg` is a known total-mismatch case and is reported as such.

## Links

- Live demo number: **+62 851-5806-4660** (WhatsApp). Access is granted on request: the bot answers only allowlisted numbers because it handles real business data and sending is limited to approved recipients, and the judges' numbers are not known in advance. Email ninoptimize@gmail.com with a WhatsApp number and it will be added; the demo video shows the full flow.
- Privacy policy: https://catatai.ardianova.com/privacy
- Health check: https://catatai.ardianova.com/health
- Video: _to be added_
- Repository: _to be added_

## Team

Nino Ardianto (ArdiaNova) — solo indie developer.
