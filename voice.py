import os, json, subprocess, tempfile, requests
from dotenv import load_dotenv

load_dotenv(".env")
URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL = "muse-voice-transcribe-1.0"

def to_wav(data):
    """Any audio bytes (Telegram voice is OGG/Opus) -> WAV 16 kHz mono 16-bit."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.bin"), os.path.join(d, "out.wav")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src,
                        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", dst], check=True, timeout=60)
        with open(dst, "rb") as f:
            return f.read()

def transcribe(wav, keywords=None, language_bias=("indonesian",)):
    req = {"mode": "PUSH_TO_TALK", "model": MODEL, "audioEncoding": "WAV"}
    if keywords:
        req["keywords"] = list(keywords)
    if language_bias:
        req["languageBias"] = list(language_bias)
    r = requests.post(URL, headers={"Authorization": "Bearer " + os.environ["META_API_KEY"]},
                      files={"request": (None, json.dumps(req), "application/json"),
                             "audio": ("voice.wav", wav, "audio/wav")}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"[{r.status_code}] {r.text[:200]}")
    return (r.json().get("transcript") or "").strip()

if __name__ == "__main__":
    import sys
    wav = open(sys.argv[1], "rb").read()
    for label, lb in (("tanpa bias", None), ("languageBias=indonesian", ("indonesian",))):
        for i in range(3):
            print(f"{label} #{i + 1}: {transcribe(wav, language_bias=lb)}")
