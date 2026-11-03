import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ["META_API_KEY"], base_url="https://api.meta.ai/v1")

t = time.time()
r = client.chat.completions.create(
    model="muse-spark-1.3",
    reasoning_effort="low",
    messages=[{"role": "user", "content": "Jawab satu kalimat bahasa Indonesia: apa itu warung?"}],
)
print(f"{time.time()-t:.1f}s")
print(r.choices[0].message.content)
