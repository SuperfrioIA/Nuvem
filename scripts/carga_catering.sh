#!/usr/bin/env bash
# Carga da volumetria de catering a partir do DW Oracle (V3.5).
#
# CONSTRUIDO NO V3.5, LIGADO NO V3.6. Este script existe e funciona, mas nao
# esta no crontab de ninguem: o servico da V3 no compose ainda nao existe (a
# imagem de hoje nao copia `catering/`), e o fuso da VM precisa ser conferido
# antes de 07h05 significar 07h05. Ver docs/DEPLOY.md, secao "Carga agendada
# da V3".
#
# Uso (na VM, do diretorio do projeto):
#   ./scripts/carga_catering.sh                  # incremental, o modo do cron
#   MODO=completa ./scripts/carga_catering.sh    # recarga cheia, sob demanda
#
# Cron sugerido (docs/DEPLOY.md) -- 30 min DEPOIS das rodadas do DW, nunca no
# mesmo horario:
#   5 7  * * * cd /home/ubuntu/nuvemIA && ./scripts/carga_catering.sh >> logs/carga_catering.log 2>&1
#   5 15 * * * cd /home/ubuntu/nuvemIA && ./scripts/carga_catering.sh >> logs/carga_catering.log 2>&1
#
# A credencial do DW (DW_USER/DW_SENHA) chega no container pelo compose, que le
# o .env da VM. Ela NUNCA aparece como argumento de linha de comando: argumento
# aparece em `ps`, em log de shell e em historico.

set -euo pipefail

# O nome do servico do compose e decisao do V3.6 -- por isso variavel, e por
# isso a checagem abaixo em vez de um erro obscuro do Compose.
SERVICO="${SERVICO_CATERING:-nuvem-cat}"
MODO="${MODO:-incremental}"

DIR_RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR_RAIZ"

registrar() { echo "[$(date -Iseconds)] $*"; }

# Uma rodada por vez. O cron dispara em horario fixo; se uma rodada atrasar
# alem da proxima, duas cargas concorrentes disputariam o upsert e a segunda
# reportaria numero que nao descreve nada. `flock` sem espera: a rodada nova
# desiste em vez de enfileirar.
TRAVA="${TMPDIR:-/tmp}/carga_catering.lock"
exec 9>"$TRAVA"
if ! flock -n 9; then
  registrar "AVISO: ja existe uma carga em andamento -- esta rodada foi PULADA"
  exit 0
fi

if [ ! -f docker-compose.yml ]; then
  registrar "ERRO: rodei em $DIR_RAIZ e nao achei docker-compose.yml"
  exit 1
fi

# Servico ausente tem que falhar dizendo o que falta. Sem isto, a mensagem do
# Compose numa VM com quatro projetos manda quem estiver de plantao para o
# lugar errado.
if ! docker compose config --services | grep -qx "$SERVICO"; then
  registrar "ERRO: o servico '$SERVICO' nao existe no compose deste projeto."
  registrar "       O servico da V3 entra no V3.6 (docs/DEPLOY.md). Servicos hoje:"
  docker compose config --services | sed 's/^/         /'
  registrar "       Se o nome for outro, use SERVICO_CATERING=<nome>."
  exit 1
fi

ARGUMENTOS=(--fonte oracle)
if [ "$MODO" = "incremental" ]; then
  ARGUMENTOS+=(--incremental)
elif [ "$MODO" != "completa" ]; then
  registrar "ERRO: MODO='$MODO' -- use 'incremental' ou 'completa'"
  exit 1
fi

registrar "iniciando carga $MODO no servico $SERVICO"

# `run --rm` e nao `exec`: a carga nao depende do processo web estar saudavel.
# Com `exec`, uma rodada morreria porque a TELA esta fora do ar, que e outro
# problema. O container e descartado no fim.
if docker compose run --rm "$SERVICO" python -m catering.carga "${ARGUMENTOS[@]}"; then
  registrar "carga $MODO concluida"
else
  codigo=$?
  # O codigo de saida sobe: agendador que nao ve falha nao serve de agendador,
  # e `cat_cargas` guarda o motivo com status 'erro'.
  registrar "ERRO: a carga $MODO falhou (codigo $codigo). Ver cat_cargas.erro"
  exit "$codigo"
fi
