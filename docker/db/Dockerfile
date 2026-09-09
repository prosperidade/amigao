# Postgres 15 + PostGIS 3.3 + pgvector — base do Amigão do Meio Ambiente.
#
# pgvector NÃO vem na imagem oficial postgis/postgis:15-3.3. Instalamos via
# o pacote Debian `postgresql-15-pgvector` para habilitar busca semântica
# sobre o knowledge_catalog (Sprint U).

FROM postgis/postgis:15-3.3

# `Check-Valid-Until=false`: o Debian bullseye foi arquivado e o Release file de
# `bullseye-security` venceu — `apt-get update` passou a sair com 100 ("Release
# file is expired"), derrubando o build da imagem e, com ele, os dois jobs de
# backend no CI. O pacote que precisamos vem do repositório pgdg
# (apt.postgresql.org), não do security; a flag só impede que a validade vencida
# de um repositório que não usamos aborte o update.
RUN apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends postgresql-15-pgvector \
    && rm -rf /var/lib/apt/lists/*
