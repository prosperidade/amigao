## Portal do Cliente

Frontend Next.js do Portal do Cliente do Amigão do Meio Ambiente.

## Desenvolvimento local

```bash
npm install
npm run dev
```

O portal sobe em `http://localhost:3000` e usa rewrite para falar com o backend em `/api/v1`.

## Variáveis relevantes

- `API_BACKEND_URL`
  URL base do backend usada nos rewrites do Next.js.
  Desenvolvimento padrão: `http://127.0.0.1:8000`
  Docker Compose: `http://api:8000`

## Docker

O `Dockerfile` usa build standalone do Next.js.

```bash
docker compose up --build
```

Serviços publicados localmente:

- Portal: `http://localhost:3000`
- API: `http://localhost:8000`
- Docs FastAPI: `http://localhost:8000/docs`
- MinIO Console: `http://localhost:9001`
- PostgreSQL: `localhost:5433`

## Build manual de produção

```bash
npm run build
npm run start
```

Para deploy fora do Docker, ajuste `API_BACKEND_URL` e a origem CORS correspondente no backend.
