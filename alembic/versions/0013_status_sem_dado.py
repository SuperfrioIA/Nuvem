"""Status `sem_dado` em processamentos_datahub (lote V2.1.1).

Achado na primeira rodada real de processamento na VM (06/ago/2026): os arquivos
`ENTRADA_MERCADORIAS_025_2601..2605` da SANCA tem cabecalho valido e ZERO linhas
de dado -- a operacao da unidade comecou em 2606. O leitor levantava excecao
nesse caso e o processamento marcava **erro**, o que estava errado por dois
motivos:

1. cinco erros permanentes no painel, para uma situacao que nunca vai ser
   corrigida (aqueles arquivos vao existir vazios pra sempre). Erro que nao se
   resolve treina quem olha a ignorar a lista -- e ai o erro de verdade passa
   batido;
2. `_ja_processado` exige status `ok`, entao os cinco eram baixados de novo em
   TODA rodada, pra sempre. E a mesma classe de problema que o lote de identidade
   de 02/ago corrigiu (o flip-flop do reprocessamento), reaparecendo por outra
   causa.

Competencia sem movimento e um estado legitimo da fonte, nao falha de leitura.
`sem_dado` e status TERMINAL: conta como processado pro "pula inalterado", entao
o arquivo para de ser rebaixado a cada rodada. Se a SANCA um dia republicar o
2601 COM dado, o `modificado_em` muda e ele reprocessa sozinho -- a chave de
frescor continua sendo a mesma.

Por que isso e migration: `status` tem CHECK inline
(`CHECK (status IN ('ok','erro','pendencia_depara'))`, migration 0006 linha 74).
Gravar 'sem_dado' sem alargar o CHECK estoura em producao na primeira SANCA
vazia. O nome da constraint e o gerado pelo Postgres pra CHECK inline.

Downgrade: volta o CHECK antigo. Antes disso, as linhas que estao em 'sem_dado'
precisam sair do estado -- viram 'erro', que e exatamente o que elas eram antes
deste lote (nao inventa estado nenhum: e o valor que o codigo antigo gravaria pro
mesmo arquivo).

Revision ID: 0013_status_sem_dado
Revises: 0012_depara_cwb3_sanca
"""

from alembic import op

revision = "0013_status_sem_dado"
down_revision = "0012_depara_cwb3_sanca"
branch_labels = None
depends_on = None

_CONSTRAINT = "processamentos_datahub_status_check"


def upgrade() -> None:
    op.execute(f"ALTER TABLE processamentos_datahub DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"""
        ALTER TABLE processamentos_datahub ADD CONSTRAINT {_CONSTRAINT}
        CHECK (status IN ('ok', 'erro', 'pendencia_depara', 'sem_dado'))
        """
    )


def downgrade() -> None:
    # 'sem_dado' volta a ser 'erro' -- o que o codigo anterior gravava pro mesmo
    # arquivo. Tem que vir ANTES de reapertar o CHECK, senao a constraint e
    # rejeitada pelas linhas existentes.
    op.execute("UPDATE processamentos_datahub SET status = 'erro' WHERE status = 'sem_dado'")
    op.execute(f"ALTER TABLE processamentos_datahub DROP CONSTRAINT {_CONSTRAINT}")
    op.execute(
        f"""
        ALTER TABLE processamentos_datahub ADD CONSTRAINT {_CONSTRAINT}
        CHECK (status IN ('ok', 'erro', 'pendencia_depara'))
        """
    )
