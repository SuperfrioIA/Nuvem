"""As duas colunas de cliente que nao identificam a linha aceitam nulo.

## Uma linha em 232.089

Em 27/ago/2026 a carga do historico completo (V3.8) trouxe o recebimento inteiro
-- 202.087 linhas, contrato de pe em todas -- e **falhou na expedicao**, numa
linha so:

    linha 143410 da fonte (SLIN_RMSPII_PRD/RMSPII/0000003623/2025/SECO 2018/
    ACERTO DE ESTOQUE - SEM CUSTO/24216040): coluna 'sk_cliente' e obrigatoria
    no contrato e veio vazia (None)

A medicao seguinte, sobre as 29 colunas obrigatorias das duas tabelas na janela
inteira, achou exatamente dois vazios -- `sk_cliente` e `nk_wms_cliente`, na
MESMA linha de 2025. Acerto de estoque sem custo nao tem cliente do outro lado,
e o DW nao resolveu a dimensao.

## Por que soltar, e nao endurecer

Nenhuma das duas identifica a linha nem aparece na tela:

  - `sk_cliente` e procedencia (a surrogate do DW). Nenhuma consulta da V3 le
    `sk_*`;
  - `nk_wms_cliente` e o codigo do cliente no WMS. A tela junta cliente por
    `nk_cliente` (`catering/consulta/recorte.py`), que nessa linha veio
    preenchido -- entao a identidade e a exibicao ficam intactas.

A nulabilidade do contrato foi medida nos CSVs de 21/ago/2026, que tinham **um
ano so**. A regra que sai disso esta escrita no `contrato.py`: obrigatoria e a
coluna sem a qual a linha nao pode ser identificada nem colocada na tela.

## As duas tabelas, nao so a expedicao

`PROCEDENCIA` e `DIMENSOES` sao compartilhadas pelos dois movimentos no
contrato, e o DW pode produzir o mesmo vazio de qualquer lado. Deixar o
recebimento estrito faria o schema divergir do contrato -- e existe teste
conferindo coluna por coluna contra o catalogo do Postgres
(`tests/test_catering_schema.py`).

## Nao mexe em dado

`DROP NOT NULL` nao reescreve linha nem pede varredura. A linha de 2025 entra na
proxima carga completa.

Revision ID: 0024_cliente_nulavel
Revises: 0023_identidade_ano_solic
"""

from alembic import op

revision = "0024_cliente_nulavel"
down_revision = "0023_identidade_ano_solic"
branch_labels = None
depends_on = None

FATOS = ("cat_fato_recebimento", "cat_fato_expedicao")
COLUNAS = ("sk_cliente", "nk_wms_cliente")


def upgrade() -> None:
    for tabela in FATOS:
        for coluna in COLUNAS:
            op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} DROP NOT NULL")


def downgrade() -> None:
    """Volta a exigir preenchimento.

    **Isto falha de proposito** se a linha do acerto de estoque ja tiver entrado:
    o Postgres recusa `SET NOT NULL` com nulo na coluna. Falhar e o
    comportamento certo -- a alternativa seria apagar linha de fato para a
    migration conseguir descer, e migration nao apaga dado do usuario."""
    for tabela in FATOS:
        for coluna in COLUNAS:
            op.execute(f"ALTER TABLE {tabela} ALTER COLUMN {coluna} SET NOT NULL")
