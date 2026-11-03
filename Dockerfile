FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py core.py corrections.py entry_edits.py store.py voice.py voice_parse.py wa_server.py ./

EXPOSE 8000

CMD ["uvicorn", "wa_server:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--workers", "1"]
