#!/usr/bin/env bash
# Pré-deploy da API em produção (Render): backup ANTES da migration.
#
# Por que existe em vez de ir direto no `preDeployCommand`: o Render não
# executa o comando por um shell e não remove as aspas da linha. Medido em
# 22/09/2026, nos dois deploys que falharam:
#   1. `python scripts/predeploy_backup.py && alembic upgrade head`
#      → o `&&` e o resto chegaram como argumentos do script (exit 2);
#   2. `sh -c "python scripts/predeploy_backup.py && alembic upgrade head"`
#      → o sh recebeu a linha inteira, COM as aspas, como nome de comando
#      (`not found`, exit 127).
# Daí a regra: o `preDeployCommand` é `sh scripts/predeploy.sh` — sem aspas,
# sem operador de shell, nada para o parser do Render errar. Encadeamento e
# quebra de linha vivem aqui dentro, onde há um shell de verdade.
#
# `set -e`: o backup falhou, a migration não roda e o pré-deploy sai != 0 —
# o Render aborta o deploy e mantém a versão anterior no ar.
set -e

python scripts/predeploy_backup.py
alembic upgrade head
