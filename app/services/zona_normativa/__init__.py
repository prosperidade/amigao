"""Zona normativa (ADR-075 + adendos A1–A5).

Catálogo global de fontes normativas com nível de autoridade, estado de
validação por versão, proveniência (a coletânea é origem, não fonte),
dispositivos endereçáveis por ID e recuperação que filtra antes de ordenar e
nunca relaxa.

Módulos:
- `identidade`     — função única de identidade normalizada (tipo+ente+órgão+número+ano).
- `desmembramento` — corte determinístico das coletâneas (sem LLM, sem OCR).
- `dispositivos`   — artigo e parágrafo como linhas endereçáveis (A1).
- `hierarquia`     — nível de autoridade por regra fixa sobre o que está gravado.
- `catalogo`       — construção do catálogo a partir do corpus legado (dry-run por padrão).
- `recuperacao`    — contrato de busca: identidade → elegível → RRF → uma vaga por dispositivo.
- `citacao`        — citação por ID verificada antes de emitir; menção sem vínculo bloqueia.
- `curadoria`      — papel de curadoria (A2), transições de status e hash chain global (A1).
- `integridade`    — hash do original e conferência de adulteração (A5).
"""
