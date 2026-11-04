# CatatAI

**A WhatsApp back-office agent for Indonesian small shops.**

Meta Global AI Developer Hackathon · Indie Developer track · Theme: *Build for Your World*

CatatAI turns the receipts, voice notes, and short messages that Indonesian shop owners already send on WhatsApp into structured sales and purchase records — no new app, no typing into a spreadsheet.

> Owners already write everything on paper and talk on WhatsApp. CatatAI meets them there.

---

## The problem

A warung or laundry owner records sales on a handwritten nota. At the end of the day they have a pile of paper and no reliable total. Bookkeeping apps fail because they require structured input: pick a date, pick a category, type each line, save. That is more work than the paper.

CatatAI inverts it: the owner sends a photo, a voice note, or one sentence, and the agent does the data entry. Before anything is saved, the agent reads the result back and asks for confirmation.

## What it does

| Input | What happens |
|---|---|
| Photo of a nota | Multimodal extraction of date, sale/purchase type, items, qty, unit, unit price, subtotal, total |
| Voice note (Bahasa Indonesia) | Transcribed, then parsed into one or more transaction entries |
| Short text, e.g. `jual es teh 10 gelas 5rb per gelas` | Parsed into the same structure |
| Correction, e.g. `yang kedua 5 bukan 3` | Patches the pending record instead of creating a new one |
| `ya` / `tidak` | Confirms or cancels the pending record |
| `/ringkasan` | Today's sales, purchases, estimated profit, and top sellers; falls back to the latest day with data when today is empty |

The agent never silently saves a guessed receipt. It flags low-confidence lines with ⚠️, asks `jual` or `beli` when the type has no explicit clue on the paper, and rejects a total that does not match the line items.

### Channels

WhatsApp is the primary channel and the one used in the demo. A **Telegram fallback** is also implemented (`telegram_bot.py`): it uses the same `agent.handle` pipeline and the same Supabase tables, supports text, photos, and voice notes, and enforces an allowlist through `TELEGRAM_ALLOWED_IDS`.

The fallback runs as a separate long-polling process (`python telegram_bot.py`). The production Docker container serves only the WhatsApp webhook, so Telegram is a local/continuity channel rather than part of the live demo.

## Architecture

```
WhatsApp user ──► Cloud API ──► FastAPI  wa_server.py ─┐
                                                       ├──► agent.handle
Telegram user ──► Bot API  ──► long poll telegram_bot ┘        │
                                                               ├── voice.py        muse-voice-transcribe-1.0
                                                               ├── core.py         muse-spark-1.3
                                                               ├── corrections.py  corrections + yes/no
                                                               ├── voice_parse.py  text/voice → entries
                                                               └── store.py        Supabase
                                                                      │
                                                                      ▼
                                                          "ya" → row saved
```

Both channels share the same pending-confirmation state and the same transaction tables, so a record started on one channel is visible on the other.

Design choices worth calling out:

- **Webhook signature is verified** with the app secret before any payload is parsed.
- **Message IDs are idempotent** (`processed_messages` table), so Meta retries never double-save.
- **Pending confirmation expires after one hour**, so stale replies cannot confirm an old record.
- **Model calls are logged** (latency, tokens, success) without ever blocking the user flow.
- **One pending record per owner**, which keeps the conversation state simple enough to reason about.

## Meta models used

| Model | Used for |
|---|---|
| `muse-spark-1.3` | Reading nota photos and extracting structured JSON; also parsing typed/transcribed transactions |
| `muse-voice-transcribe-1.0` | Transcribing WhatsApp voice notes in Bahasa Indonesia |
| `sam-3.1` | Available in the product scope for product/stock segmentation; not required in the core nota flow |
| `muse-image-1.0` | Available for catalog visuals; not required in the core nota flow |

The shipped, demoed path uses `muse-spark-1.3` and `muse-voice-transcribe-1.0`. The other two are part of the product roadmap in the PRD, not claims about the current demo.

## Evaluation

We evaluated the extraction path on **15 Indonesian nota photos**. Ground truth was written by hand before running the model. Inputs were used unmodified.

| Field | Correct | Total | Accuracy |
|---|---|---|---|
| name | 39 | 41 | 95.1% |
| qty | 39 | 41 | 95.1% |
| unit_price | 40 | 41 | 97.6% |
| subtotal | 39 | 41 | 95.1% |
| total | 14 | 15 | 93.3% |
| type (sale/purchase/unknown) | 15 | 15 | 100.0% |
| item count | — | — | 100.0% |

- Overall field accuracy: **95.7%**
- Confidence flag (low-confidence marker ⚠️): recall **1.00**, precision **0.50**. It catches every real error but also flags some correct lines, so the owner sometimes confirms a line that was fine.
- Average latency: **21.4 s** per nota (model calls only; WhatsApp delivery excluded)
- Tokens: 74,863 in / 38,238 out
- Estimated model cost for the full run: **$0.2561**

The single total failure is `003.jpg`: the model read the right items but the printed total did not match their sum. The agent flagged it as a mismatch instead of saving it silently.

**Honest note on the eval set:** the 15 photos are synthetic nota images created for evaluation, not real customer receipts. The one real receipt used in the demo is kept private and is not part of the published eval set. The photos themselves and the raw per-image model outputs are gitignored; the ground truth and the aggregate report below are published.

Reproduce from the repository root after placing the 15 nota photos in `images/` as `001.jpg` … `015.jpg` (the photos are not published):

```bash
python eval/run_eval.py
```

`eval/truth.json` contains the ground truth, `eval/file_map.json` maps file names to truth entries, and `results/eval_report.md` is the generated report.

## Demo

- Video: https://youtu.be/lWIY0Qf5vCY
- Live number: **+62 851-5806-4660** (WhatsApp)
- **Access:** the bot answers only numbers on an allowlist (it handles real business data, and sending is limited to approved recipients). Judges: email ninoptimize@gmail.com with your WhatsApp number and I will add it, or watch the demo video.

The demo records the real flow end to end: greeting → photo of a real laundry nota → read-back → `ya` → saved row → `/ringkasan`.

**Privacy in the demo:** the customer name on the real nota is redacted in post-production. The original image is never published. This is disclosed here and in the video description. Redaction is applied only to publication material — evaluation always runs on unmodified originals, because redacting the input would invalidate the accuracy numbers.

## Run it locally

Requirements: Python 3.12, `ffmpeg` (for voice notes), a Supabase project, and a Meta app with WhatsApp Cloud API access.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the values
uvicorn wa_server:app --host 0.0.0.0 --port 8000
```

Optional Telegram fallback, in a second terminal:

```bash
python telegram_bot.py
```

Apply `schema.sql` to Supabase before the first run.

### Environment variables

| Variable | Purpose |
|---|---|
| `META_API_KEY` | Meta Model API key (`https://api.meta.ai/v1`) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (server-side only) |
| `WHATSAPP_ACCESS_TOKEN` | System-user token with `whatsapp_business_messaging` + `whatsapp_business_management` |
| `WHATSAPP_PHONE_NUMBER_ID` | Cloud API phone number ID |
| `WHATSAPP_WABA_ID` | WhatsApp Business Account ID |
| `WHATSAPP_APP_SECRET` | App secret, used to verify webhook signatures |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token |
| `WHATSAPP_ALLOWED_NUMBERS` | Comma-separated E.164 numbers allowed to use the bot |
| `WHATSAPP_API_VERSION` | Graph API version, e.g. `v25.0` |

Telegram variables are optional and only used by the fallback channel.

### WhatsApp setup

1. Create a Meta app, add the WhatsApp product, and link a WABA and phone number.
2. Set the callback URL to `https://<your-host>/webhook` and subscribe to the `messages` field.
3. Use the same value for `WHATSAPP_VERIFY_TOKEN` in the app dashboard and `.env`.
4. Put the app in **Live** mode; development mode does not deliver production webhooks.
5. Send the first message from the owner's phone. Free-form business replies are only allowed inside the 24-hour customer service window.

### Deploy

`Dockerfile` and `docker-compose.yml` run the service on `127.0.0.1:8000`; a reverse proxy terminates TLS.

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8000/health
```

`deploy/nginx-catatai.conf` is the nginx site used in production. `GET /privacy` serves the privacy policy required for app publishing.

## Repository layout

```
wa_server.py       FastAPI webhook, signature check, media download, replies
telegram_bot.py    Telegram fallback channel (long polling, same agent/store)
agent.py           routing, greetings, pending confirmation, voice flow
core.py            nota prompt, extraction, validation, orientation retry, reply text
corrections.py     edit operations and yes/no classification
voice_parse.py     text/voice → transaction entries
store.py           Supabase persistence, summary, model-call log
voice.py           audio conversion + transcription
chat.py            local CLI for testing without a messaging channel
schema.sql         database schema
eval/              ground truth, file map, evaluation runner
deploy/            nginx config
```

## Limitations

- Free-form replies require the 24-hour WhatsApp customer service window; outside it, a template message is needed.
- The Telegram fallback is implemented and shares the same agent and database, but it is not running inside the production container. It is started separately when needed.
- The bot reads one pending record at a time. That is deliberate, but it means two receipts sent back to back need two confirmations.
- Handwriting quality still matters. Low-confidence items are flagged, not guessed.
- `003.jpg` in the eval set is a known total-mismatch case; the agent flags it rather than correcting it silently.
- Sale/purchase type is inferred only from explicit clues on the paper. When there is no buyer line and no supplier mark, the agent asks instead of defaulting to `sale`.
- Product/stock segmentation with `sam-3.1` and catalog images with `muse-image-1.0` are scoped in the PRD but not part of the demoed path.

## License

Code is released under the [MIT License](LICENSE). Receipt images and customer data are not covered by that license and are not published.
