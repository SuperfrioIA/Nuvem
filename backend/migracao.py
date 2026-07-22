"""Migracao de schema no startup (Alembic) — Lote R0.

Tres estados possiveis do banco, detectados pelo information_schema:

- **gerenciado**: tabela `alembic_version` existe -> so `upgrade head`.
- **novo**: nenhuma tabela conhecida -> `upgrade head` (a baseline cria tudo).
- **legado**: tabelas do init_db antigo sem `alembic_version` -> validacao do
  schema ANTES do stamp: as 12 tabelas esperadas precisam existir com as
  colunas obrigatorias. Qualquer divergencia ABORTA sem stamp automatico, com
  erro claro no log e orientacao de contingencia (docs/DEPLOY.md). O stamp so
  acontece se o schema legado bater com a baseline esperada.

Colunas e tabelas EXTRAS nao sao erro (validacao de presenca, nao de
igualdade estrita).
"""

import logging
import os
from pathlib import Path

import psycopg2
from alembic import command
from alembic.config import Config

log = logging.getLogger("nuvem.migracao")

BASELINE = "0001_baseline"
RAIZ = Path(__file__).resolve().parent.parent  # raiz do repo (tem alembic.ini)

# Colunas obrigatorias por tabela — o minimo que o codigo atual usa. Deve
# refletir a baseline (alembic/versions/0001_baseline.py); os testes conferem.
SCHEMA_ESPERADO = {
    "conectores": {"id", "tipo", "nome", "config", "ativo", "criado_em"},
    "armazens": {"id", "nome", "sigla", "ativo"},
    "metricas": {"id", "nome", "unidade"},
    "depara_armazem": {"id", "conector_id", "armazem_na_fonte", "armazem_id"},
    "depara_pendencias": {
        "id", "conector_id", "armazem_na_fonte", "primeira_vez_em", "ultima_vez_em",
    },
    "modelos_importacao": {"id", "conector_id", "nome", "mapeamento", "ativo", "criado_em"},
    "medidas": {
        "id", "metrica_id", "armazem_id", "competencia", "valor", "conector_id", "atualizado_em",
    },
    "scores": {
        "id", "metrica_id", "armazem_id", "competencia",
        "media", "desvio_padrao", "z_score", "estado", "calculado_em",
    },
    "execucoes": {
        "id", "conector_id", "modelo_id", "origem", "iniciado_em", "finalizado_em",
        "status", "linhas_lidas", "linhas_gravadas", "erro", "arquivo_path",
    },
    "clientes": {"id", "nk_erp", "nome", "catering"},
    "catalogo_fontes": {
        "id", "chave", "nome", "descricao", "tabela_origem", "tipo_origem", "grao", "modelo_id",
    },
    "catalogo_colunas": {"id", "fonte_id", "coluna", "significado", "papel"},
}


def _config() -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    return cfg


def _colunas_existentes() -> dict[str, set[str]]:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            resultado: dict[str, set[str]] = {}
            for tabela, coluna in cur.fetchall():
                resultado.setdefault(tabela, set()).add(coluna)
            return resultado
    finally:
        conn.close()


def validar_schema_legado(existentes: dict[str, set[str]]) -> list[str]:
    """Compara o schema encontrado com a baseline esperada. Devolve a lista de
    divergencias (vazia = schema legado valido para stamp)."""
    problemas = []
    for tabela, obrigatorias in SCHEMA_ESPERADO.items():
        if tabela not in existentes:
            problemas.append(f"tabela ausente: {tabela}")
            continue
        faltando = obrigatorias - existentes[tabela]
        if faltando:
            problemas.append(f"colunas ausentes em {tabela}: {', '.join(sorted(faltando))}")
    return problemas


def migrar() -> None:
    existentes = _colunas_existentes()
    cfg = _config()

    if "alembic_version" in existentes:
        log.info("banco gerenciado pelo Alembic — aplicando migrations pendentes")
        command.upgrade(cfg, "head")
        return

    tabelas_legadas = SCHEMA_ESPERADO.keys() & existentes.keys()
    if not tabelas_legadas:
        log.info("banco novo — criando o schema pela baseline (upgrade head)")
        command.upgrade(cfg, "head")
        return

    problemas = validar_schema_legado(existentes)
    if problemas:
        detalhe = "; ".join(problemas)
        log.error(
            "banco legado NAO bate com a baseline esperada — stamp automatico ABORTADO, "
            "nada foi alterado no banco. Divergencias: %s. Contingencia: docs/DEPLOY.md, "
            "secao 'Migrations (Alembic)'.",
            detalhe,
        )
        raise RuntimeError(
            f"schema legado divergente da baseline ({detalhe}) — "
            "ver docs/DEPLOY.md, secao 'Migrations (Alembic)'"
        )

    log.info(
        "banco legado validado (%d tabelas, colunas obrigatorias presentes) — "
        "stamp da baseline + upgrade",
        len(SCHEMA_ESPERADO),
    )
    command.stamp(cfg, BASELINE)
    command.upgrade(cfg, "head")
