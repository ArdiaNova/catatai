import os, json, time, base64, io, glob
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageOps

load_dotenv()
client = OpenAI(api_key=os.environ["META_API_KEY"], base_url="https://api.meta.ai/v1")
MODEL = "muse-spark-1.3"
EFFORT = "medium"

PROMPT = """You are reading a photo of a handwritten or printed Indonesian shop receipt (nota) or ledger page.
Extract the data into JSON with exactly this shape:
{
  "is_nota": true,
  "date": "YYYY-MM-DD or null",
  "type": "sale" | "purchase" | "unknown",
  "items": [{"name": str, "qty": number, "unit_price": integer, "subtotal": integer, "confidence": 0.0-1.0}],
  "total": integer or null,
  "total_confidence": 0.0-1.0,
  "notes": "short remark about anything unclear"
}
Rules:
- Amounts are Indonesian Rupiah as plain integers. "87.500" or "87,500" means 87500. "5rb" or "5k" means 5000.
- Never guess. If a field is hard to read, give it a low confidence (below 0.6) and explain in notes.
- Keep item names in the original Indonesian wording.
- If the image is not a receipt or ledger, set is_nota to false and items to [].
Reply with JSON only."""

def encode(path):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGB")
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

os.makedirs("results", exist_ok=True)
files = sorted(f for f in glob.glob("images/*") if os.path.isfile(f))
print(f"{len(files)} files, model={MODEL}, effort={EFFORT}\n")
print(f"{'file':12} {'sec':>5} {'items':>5} {'total':>10} {'sum_ok':>6} {'min_conf':>8} {'tok_in':>7} {'tok_out':>7}")

for f in files:
    base = os.path.basename(f)
    name = os.path.splitext(base)[0]
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=MODEL,
            reasoning_effort=EFFORT,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encode(f)}},
            ]}],
        )
        dt = time.time() - t
        data = parse(r.choices[0].message.content)
        with open(f"results/{name}.json", "w") as out:
            json.dump(data, out, indent=2, ensure_ascii=False)
        items = data.get("items") or []
        s = sum((i.get("subtotal") or 0) for i in items)
        total = data.get("total")
        confs = [i["confidence"] for i in items if isinstance(i.get("confidence"), (int, float))]
        minc = f"{min(confs):.2f}" if confs else "-"
        u = getattr(r, "usage", None)
        tin = getattr(u, "prompt_tokens", "-")
        tout = getattr(u, "completion_tokens", "-")
        flag = "" if data.get("is_nota", True) else "  (not a nota)"
        print(f"{base:12} {dt:5.1f} {len(items):5} {str(total):>10} {str(total == s):>6} {minc:>8} {tin:>7} {tout:>7}{flag}")
    except Exception as e:
        print(f"{base:12} ERROR {type(e).__name__}: {str(e)[:200]}")
