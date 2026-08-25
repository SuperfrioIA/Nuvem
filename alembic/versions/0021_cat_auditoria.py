"""V3.3 -- `cat_auditoria`: quem baixou o que, com qual recorte.

## O que e auditado, e o que nao e

Decisao da Maria em 24/ago/2026: **so login e download**. Consulta a consulta
nao -- gera volume e ninguem le. Uma tabela de auditoria que ninguem consegue
ler deixa de ser auditoria e passa a ser custo de escrita.

## Tabela propria, nao a `eventos_auditoria` da V2

A V2 esta congelada (Maria, 24/ago/2026) e o V3.2 acabou de fixar a separacao
com teste (`test_app_da_v3_nao_depende_do_app_da_v2`). Pendurar a auditoria da
V3 no schema da V2 desfaria exatamente isso: o dia em que a V2 sair da VM, a
auditoria da V3 sairia junto. O prefixo `cat_` mantem a fronteira visivel.

## `usuario` nulavel, de proposito

Login e papeis sao o V3.4 -- neste lote nao existe identidade. O que tem valor
agora **nao depende dela**: qual recorte foi baixado, quantas linhas sairam,
quando, e em qual formato. O V3.4 preenche a coluna; o resto do registro nao
muda de forma.

Deixar a coluna `NOT NULL DEFAULT 'anonimo'` seria pior: inventaria um ator que
nao existe, e depois ninguem saberia distinguir "antes do login" de "usuario
apagado".

## Registra no inicio e fecha no fim

Mesmo padrao do `cat_cargas`: a linha nasce `rodando`, com o recorte, e fecha
`ok` com a contagem ou `erro` com a mensagem. Download que morreu no meio e
justamente o que se quer ver numa auditoria -- se o registro fosse escrito
apenas no fim, um download interrompido nao deixaria rastro nenhum, e um que
falhou apareceria como concluido.

Por isso o registro tambem vive em **conexao propria** no codigo: o streaming
pode morrer no meio, e o rastro tem que sobreviver a isso.

## Indice

Um, por `(evento, criado_em)`: as duas perguntas que essa tabela responde sao
"quem baixou hoje" e "todos os downloads de tal periodo". Indice que nao serve
consulta nenhuma custa escrita e engana quem le o schema -- mesma disciplina da
0019 e da V2.1.

Revision ID: 0021_cat_auditoria
Revises: 0020_cat_cargas_fonte
"""

from alembic import op

revision = "0021_cat_auditoria"
down_revision = "0020_cat_cargas_fonte"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cat_auditoria (
            id          BIGSERIAL PRIMARY KEY,
            criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
            terminado_em TIMESTAMPTZ,
            evento      TEXT NOT NULL,
            -- nulo ate o V3.4 (login). Ver docstring: nao inventar ator.
            usuario     TEXT,
            -- o recorte exato dos filtros da tela, como a consulta o recebeu
            recorte     JSONB NOT NULL DEFAULT '{}',
            formato     TEXT,
            linhas      INTEGER,
            ip          TEXT,
            status      TEXT NOT NULL DEFAULT 'rodando',
            erro        TEXT,
            CONSTRAINT ck_cat_auditoria_evento CHECK (evento IN
                ('download', 'login')),
            CONSTRAINT ck_cat_auditoria_status CHECK (status IN
                ('rodando', 'ok', 'erro')),
            CONSTRAINT ck_cat_auditoria_formato CHECK (formato IS NULL OR formato IN
                ('csv', 'xlsx'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_cat_auditoria_evento "
        "ON cat_auditoria (evento, criado_em)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE cat_auditoria")
