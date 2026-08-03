#!/usr/bin/env bash
# Backup local do Postgres (pg_dump dentro do container) + dos arquivos
# retidos do upload manual. Bloco G / G1 (V1.8): mecanismo local e testado;
# copia para fora da VM fica pendencia declarada (decisao da Maria, ver
# docs/DEPLOY.md, secao "Backup e restauracao").
#
# Uso: scripts/backup.sh
# Cron sugerido na VM (docs/DEPLOY.md):
#   0 3 * * * cd /home/ubuntu/nuvemIA && ./scripts/backup.sh >> backups/backup.log 2>&1

set -euo pipefail

RETENCAO_DIAS="${RETENCAO_DIAS:-14}"

DIR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_RAIZ"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

UPLOADS_HOST_PATH="${UPLOADS_HOST_PATH:-./data/uploads}"
DIR_BACKUP="$DIR_RAIZ/backups"
mkdir -p "$DIR_BACKUP"

CARIMBO="$(date +%Y%m%d_%H%M%S)"

echo "[$(date -Iseconds)] iniciando backup ($CARIMBO)"

docker compose exec -T nuvem-db pg_dump -U nuvem nuvem | gzip > "$DIR_BACKUP/nuvem_${CARIMBO}.sql.gz"
echo "[$(date -Iseconds)] dump do banco: $DIR_BACKUP/nuvem_${CARIMBO}.sql.gz"

if [ -d "$UPLOADS_HOST_PATH" ]; then
  tar czf "$DIR_BACKUP/uploads_${CARIMBO}.tar.gz" -C "$(dirname "$UPLOADS_HOST_PATH")" "$(basename "$UPLOADS_HOST_PATH")"
  echo "[$(date -Iseconds)] arquivo dos uploads: $DIR_BACKUP/uploads_${CARIMBO}.tar.gz"
else
  echo "[$(date -Iseconds)] aviso: diretorio de uploads '$UPLOADS_HOST_PATH' nao encontrado -- pulado"
fi

echo "[$(date -Iseconds)] limpando backups com mais de ${RETENCAO_DIAS} dias"
find "$DIR_BACKUP" -maxdepth 1 -type f \( -name 'nuvem_*.sql.gz' -o -name 'uploads_*.tar.gz' \) -mtime "+${RETENCAO_DIAS}" -print -delete

echo "[$(date -Iseconds)] backup concluido"
