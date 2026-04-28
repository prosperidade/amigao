# Postgres 15 + PostGIS 3.3 + pgvector — base do Amigão do Meio Ambiente.
#
# pgvector NÃO vem na imagem oficial postgis/postgis:15-3.3. Instalamos via
# o pacote Debian `postgresql-15-pgvector` para habilitar busca semântica
# sobre o knowledge_catalog (Sprint U).

FROM postgis/postgis:15-3.3

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-15-pgvector \
    && rm -rf /var/lib/apt/lists/*
