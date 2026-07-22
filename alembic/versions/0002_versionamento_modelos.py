"""Lote R1 — Fontes logicas + versionamento real dos modelos de importacao.

Aditivo e nao destrutivo (preserva os dados de producao):

- catalogo_fontes ganha `ativo` (a fonte logica pode ser ligada/desligada).
- modelos_importacao ganha `fonte_id` (o modelo pertence a uma fonte logica).
- nova `modelo_versoes`: uma linha por versao IMUTAVEL do modelo, com o
  mapeamento em JSON, hash_config, ativo/padrao e criado_em. Editar um modelo =
  criar versao nova; versao antiga nunca muda.
- execucoes ganha `modelo_versao_id`: a versao EXATA usada naquela rodada.

Conversao dos modelos atuais: cada modelo existente vira a versao 1 (ativa e
padrao), com o mapeamento que ja estava salvo. As execucoes antigas que tinham
`modelo_id` passam a apontar pra v1 desse modelo (quando possivel; execucao sem
modelo fica com versao NULL, preservada). Se algum modelo nao puder ser
convertido com seguranca (mapeamento invalido), a migration ABORTA sem alterar
nada (roda dentro da transacao do Alembic).

Revision ID: 0002_versionamento_modelos
Revises: 0001_baseline
"""

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "0002_versionamento_modelos"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _hash(mapeamento: dict) -> str:
    """Igual a backend/versoes.hash_mapeamento — mantido inline aqui de proposito:
    uma migration precisa ser congelada no tempo, nao seguir refatoracoes futuras
    do runtime. Um teste trava a igualdade entre os dois hoje."""
    canonico = json.dumps(mapeamento, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def upgrade() -> None:
    # 1) fonte logica: catalogo_fontes ganha `ativo`
    op.execute("ALTER TABLE catalogo_fontes ADD COLUMN ativo BOOLEAN NOT NULL DEFAULT true")

    # 2) o modelo pertence a uma fonte logica
    op.execute(
        "ALTER TABLE modelos_importacao ADD COLUMN fonte_id INTEGER REFERENCES catalogo_fontes(id)"
    )

    # 3) versoes imutaveis do modelo
    op.execute(
        """
        CREATE TABLE modelo_versoes (
            id SERIAL PRIMARY KEY,
            modelo_id INTEGER NOT NULL REFERENCES modelos_importacao(id),
            versao INTEGER NOT NULL,
            mapeamento JSONB NOT NULL,
            hash_config TEXT NOT NULL,
            ativo BOOLEAN NOT NULL DEFAULT true,
            padrao BOOLEAN NOT NULL DEFAULT false,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (modelo_id, versao),
            CONSTRAINT padrao_exige_ativo CHECK (ativo OR NOT padrao)
        )
        """
    )
    # no maximo uma versao padrao por modelo
    op.execute(
        "CREATE UNIQUE INDEX uq_modelo_versao_padrao ON modelo_versoes (modelo_id) WHERE padrao"
    )

    # 4) a execucao grava a versao exata usada
    op.execute(
        "ALTER TABLE execucoes ADD COLUMN modelo_versao_id INTEGER REFERENCES modelo_versoes(id)"
    )

    # 5) conversao dos modelos atuais -> v1 (ativa e padrao)
    bind = op.get_bind()
    modelos = bind.execute(
        sa.text("SELECT id, mapeamento FROM modelos_importacao ORDER BY id")
    ).fetchall()
    for modelo_id, mapa in modelos:
        if isinstance(mapa, str):
            mapa = json.loads(mapa)
        if not isinstance(mapa, dict):
            raise RuntimeError(
                f"modelo_importacao id={modelo_id}: mapeamento invalido "
                f"({type(mapa).__name__}) — conversao para v1 abortada, "
                "nada foi alterado no banco"
            )
        bind.execute(
            sa.text(
                "INSERT INTO modelo_versoes "
                "(modelo_id, versao, mapeamento, hash_config, ativo, padrao) "
                "VALUES (:mid, 1, CAST(:mapa AS jsonb), :h, true, true)"
            ),
            {"mid": modelo_id, "mapa": json.dumps(mapa), "h": _hash(mapa)},
        )

    # execucoes antigas com modelo apontam pra v1 desse modelo (quando possivel)
    bind.execute(
        sa.text(
            "UPDATE execucoes e SET modelo_versao_id = mv.id "
            "FROM modelo_versoes mv "
            "WHERE mv.modelo_id = e.modelo_id AND mv.versao = 1 "
            "AND e.modelo_id IS NOT NULL AND e.modelo_versao_id IS NULL"
        )
    )


def downgrade() -> None:
    op.execute("ALTER TABLE execucoes DROP COLUMN IF EXISTS modelo_versao_id")
    op.execute("DROP TABLE IF EXISTS modelo_versoes")
    op.execute("ALTER TABLE modelos_importacao DROP COLUMN IF EXISTS fonte_id")
    op.execute("ALTER TABLE catalogo_fontes DROP COLUMN IF EXISTS ativo")
