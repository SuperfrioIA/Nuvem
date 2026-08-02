"""Bloco D (V1.4) -- Laboratorio de Insights: sessao de analise.

Uma tabela nova, puramente aditiva. Guarda o que a secao 9.6 do direcionamento
exige rastrear na parte que existe no V1.4 (selecao, filtros, perfil,
limites); mensagens/respostas/modelo/parametros/feedback entram no V1.5
(Bloco E), em tabela propria -- nao ha coluna vazia esperando aqui.

- selecao: o que o usuario escolheu (item_ids do inventario, familia, arquivos)
  -- registrado como PEDIDO, nao como resultado.
- filtros: filiais/clientes/competencias pedidos.
- limites: os limites efetivamente aplicados (quantidade, linhas, tamanho,
  tempo) -- o perfil precisa dizer que foi truncado, se foi.
- perfil: o perfil deterministico completo (colunas, tipos, nulos, distintos,
  min/max, somas permitidas, unidades, duplicidades, chaves candidatas,
  cobertura temporal, filiais, clientes, granularidade, qualidade, limitacoes
  e amostra). JSONB porque o perfil e um documento de leitura, nunca chave de
  junção -- consultar por dentro dele nao e caso de uso do V1.4.
- usuario: hoje sempre 'admin' -- a autenticacao do projeto e senha unica, sem
  identidade por pessoa (limitacao declarada; acesso por usuario e do V1.8).

status: 'perfilada' e o unico estado que o V1.4 produz; 'em_analise' (chat do
V1.5), 'descartada' e 'aprovada' (V1.6) ja entram no CHECK pra nao exigir
migration de enum no bloco seguinte. Fora o CHECK, nenhuma coluna existe "pra
depois": toda coluna aqui e escrita pelo V1.4.

Revision ID: 0007_laboratorio_sessoes
Revises: 0006_persistencia_datahub
"""

from alembic import op

revision = "0007_laboratorio_sessoes"
down_revision = "0006_persistencia_datahub"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE laboratorio_sessoes (
            id SERIAL PRIMARY KEY,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
            usuario TEXT NOT NULL,
            titulo TEXT,
            selecao JSONB NOT NULL,
            filtros JSONB,
            limites JSONB NOT NULL,
            perfil JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'perfilada'
                CHECK (status IN ('perfilada', 'em_analise', 'descartada', 'aprovada'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_laboratorio_sessoes_criado_em ON laboratorio_sessoes (criado_em DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_laboratorio_sessoes_criado_em")
    op.execute("DROP TABLE IF EXISTS laboratorio_sessoes")
