#!/usr/bin/env bash
# Restaura um dump gerado por scripts/backup.sh. DESTRUTIVO: apaga o schema
# 'public' atual do banco 'nuvem' antes de restaurar (mesmo padrao da fixture
# banco_vazio da suite de testes -- garante restauracao idempotente, sem
# conflito com objetos que ja existem). Bloco G / G1 (V1.8).
#
# Uso: scripts/restore.sh caminho/para/nuvem_AAAAMMDD_HHMMSS.sql.gz

set -euo pipefail

DIR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_RAIZ"

ARQUIVO="${1:-}"
if [ -z "$ARQUIVO" ]; then
  echo "uso: scripts/restore.sh <arquivo.sql.gz>" >&2
  exit 1
fi
if [ ! -f "$ARQUIVO" ]; then
  echo "arquivo nao encontrado: $ARQUIVO" >&2
  exit 1
fi

echo "Isto vai APAGAR o conteudo atual do banco 'nuvem' e substituir por $ARQUIVO."
read -r -p "Digite 'restaurar' para confirmar: " CONFIRMACAO
if [ "$CONFIRMACAO" != "restaurar" ]; then
  echo "cancelado."
  exit 1
fi

echo "[$(date -Iseconds)] zerando schema public"
docker compose exec -T nuvem-db psql -v ON_ERROR_STOP=1 -U nuvem nuvem -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "[$(date -Iseconds)] restaurando $ARQUIVO"
# ON_ERROR_STOP e essencial aqui: sem ele, psql segue rodando os comandos
# seguintes do dump mesmo apos um erro no meio e devolve exit code 0 --
# restauracao parcial se passando por sucesso.
gunzip -c "$ARQUIVO" | docker compose exec -T nuvem-db psql -v ON_ERROR_STOP=1 -U nuvem nuvem

echo "[$(date -Iseconds)] restauracao concluida"
