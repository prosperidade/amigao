FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg — compressão automática de áudio de reunião (dívida #201 · ADR-060).
# O provedor de transcrição recusa acima de 25 MB, e uma gravação de uma hora em
# WAV passa disso com folga. Sem esta ferramenta a saída era pedir à consultora
# que "reenviasse em mono, 64 kbps" — instrução que só serve a quem sabe o que é
# bitrate. Com ela, o sistema comprime sozinho e ela nunca ouve falar do assunto.
# Bônus: formatos que o provedor não lê (.amr de gravador antigo, .wma) passam a
# ser transcritos em vez de recusados.
# `--no-install-recommends` mantém o custo em ~60 MB (só o binário e os codecs).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY seed.py ./

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
