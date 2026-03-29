# Checklist de Segredos e SMTP para Produção

## Arquivo-base

Use `.env.production.example` como referência e preencha os valores reais fora do repositório.

## Variáveis obrigatórias

- `SECRET_KEY`: chave JWT com no mínimo 32 caracteres
- `POSTGRES_PASSWORD`: senha forte do banco
- `MINIO_ACCESS_KEY`: credencial de acesso ao storage
- `MINIO_SECRET_KEY`: segredo do storage
- `MINIO_PUBLIC_URL`: URL pública usada nas presigned URLs
- `SMTP_HOST`: host do provedor SMTP
- `SMTP_USER`: usuário SMTP
- `SMTP_PASSWORD`: senha ou token SMTP
- `EMAILS_FROM_EMAIL`: remetente válido do domínio real
- `EMAILS_FROM_NAME`: nome de exibição do remetente
- `CLIENT_PORTAL_URL`: URL final do portal do cliente
- `BACKEND_CORS_ORIGINS`: lista de domínios finais permitidos

## Regras já validadas pelo backend

- produção não aceita `SECRET_KEY` vazia, curta ou default insegura
- produção não aceita `MINIO_ACCESS_KEY` e `MINIO_SECRET_KEY` com valor `minioadmin`
- produção não aceita `MINIO_PUBLIC_URL` local
- produção não aceita `CLIENT_PORTAL_URL` local
- produção não aceita `BACKEND_CORS_ORIGINS` com hosts locais
- produção não aceita SMTP ausente
- produção não aceita `EMAILS_FROM_NAME` vazio

## Geração recomendada

Para gerar uma `SECRET_KEY` forte localmente:

```bash
openssl rand -hex 32
```
