# Slides for the demo video

Two 1920×1080 cards for section 8 of `DEMO.md`:

| File | Use |
|---|---|
| `eval.html` / `eval.png` | Evaluation results, 2:22–2:30 |
| `close.html` / `close.png` | Closing card, 2:30–2:35 |

The PNGs are already rendered at 1920×1080. Open the HTML files directly in a browser if you want to edit the text, then re-render.

## Re-render with Firefox headless

Firefox refuses to start headless while a normal Firefox is running, so use a separate profile:

```bash
cd slides
mkdir -p /tmp/catatai-ff
firefox --headless --profile /tmp/catatai-ff --window-size=1920,1080 \
  --screenshot "$PWD/eval.png" "file://$PWD/eval.html"
firefox --headless --profile /tmp/catatai-ff --window-size=1920,1080 \
  --screenshot "$PWD/close.png" "file://$PWD/close.html"
```

## Editing notes

- Canvas is **16:9**. If the final video is vertical, put the card on a 9:16 canvas with the card scaled to fit, or export a 1080×1920 version.
- No external fonts or network requests, so rendering is stable offline.
- Keep the word **sintetis** on the evaluation card. The 15 nota are synthetic, not customer receipts.
- Numbers come from `results/eval_report.md`. Do not round 95.7 to 96.
