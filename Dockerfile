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
#
# postgresql-client — pg_dump/pg_restore do backup de pré-deploy
# (scripts/predeploy_backup.py). A major TEM de ser >= a do servidor: produção
# (Supabase) roda PostgreSQL 17.6 e pg_dump mais antigo recusa o dump. O Debian
# não traz a 17, então vem do repositório oficial PGDG. Subir PG_CLIENT_MAJOR
# junto com qualquer upgrade de major do Supabase.
ARG PG_CLIENT_MAJOR=17
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-${PG_CLIENT_MAJOR} \
    && pg_dump --version | grep -q " ${PG_CLIENT_MAJOR}\." \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
# A ontologia é MÉTODO, não documentação: `capability_manifest("extrator")`
# exige o vocabulário e guarda o hash dele no manifesto do job. Fora da imagem,
# o extrator morre em "capacidade_insuficiente" antes de ler qualquer
# documento — medido em produção em 22/09/2026, casos #23 e #25 (dívida #260).
COPY docs/arquitetura/ONTOLOGIA_REGENTE_v1.md ./docs/arquitetura/
COPY seed.py ./

RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
