"""Lote de correcao -- identidade do arquivo do DataHub e de-para por unidade.

A fonte foi reestruturada em 31/jul/2026 e passou a ter quatro unidades
(RMSPII/RJ/CWB3/SANCA) publicando com a MESMA convencao de nome: existem 7
arquivos `ENTRADA_MERCADORIAS_001_26MM.xlsx` em RMSPII e em CWB3, mesmo codigo
de filial, armazens diferentes. Duas premissas do Bloco C cairam junto:

1. "o nome identifica o arquivo" -- `processamentos_datahub` tinha
   UNIQUE(arquivo), entao os dois homonimos disputavam o mesmo registro: o
   "pula inalterados" flip-flopava e a linhagem em `medidas_recebidas` (que e
   append-only) ficaria com o armazem errado, de forma permanente.
2. "o codigo de filial identifica o armazem" -- `001` existe em duas unidades e
   o de-para mandava as duas pra RMSPII.

Duas mudancas, as duas de identidade:

- `processamentos_datahub`: a chave passa a ser `item_id` (o id do item do
  Graph, que ja existia como coluna NOT NULL -- nao ha backfill). Ele e estavel
  a renomeacao e a movimentacao, entao mover um arquivo no SharePoint deixa de
  criar entidade nova. `arquivo` continua na tabela como atributo mutavel de
  exibicao. Colunas novas `caminho` e `unidade` (nullable: as linhas antigas
  nao tem o dado; o codigo sempre as escreve daqui em diante).
- `depara_armazem`: o campo `armazem_na_fonte` do conector do DataHub deixa de
  significar "codigo de filial" e passa a significar "codigo de origem
  QUALIFICADO pela unidade" (`RMSPII/001`, `CWB3/001`, `SANCA/025`,
  `RJ/004-003`). E texto livre desde o 0001, entao a mudanca e de semantica e
  de dado -- nao de schema. O UPDATE preserva o `armazem_id` de cada linha (um
  ajuste manual de de-para sobrevive), diferente de um delete+reseed.

Em producao isto e no-op: o conector `sharepoint_datahub` so nasce com os seeds
do Bloco C, que ainda nao subiram (a VM esta em 0004). O UPDATE existe pros
bancos de desenvolvimento, onde o de-para ja foi semeado sem qualificacao.

Escopo do UPDATE: exatamente os tres codigos que o seed do Bloco C escreve
(001/015/016 -> RMSPII). Uma linha de de-para acrescentada a mao fora desses
tres nao e tocada -- ficaria inerte (nenhuma consulta usa mais codigo nu) e
precisa ser recadastrada qualificada. As pendencias sao apagadas em vez de
prefixadas: sao diagnostico, nao cadastro, e nao da pra afirmar a unidade de
uma pendencia antiga (uma pendencia de `025` e da SANCA, nao da RMSPII) --
a proxima rodada as recria com o codigo certo.

Revision ID: 0008_identidade_datahub
Revises: 0007_laboratorio_sessoes
"""

from alembic import op

revision = "0008_identidade_datahub"
down_revision = "0007_laboratorio_sessoes"
branch_labels = None
depends_on = None

# unidade da arvore legada: tudo que o Bloco C semeou/processou veio dela (era
# a pasta inteira antes da reestruturacao)
_UNIDADE_LEGADA = "RMSPII"
_CODIGOS_SEMEADOS = ("001", "015", "016")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE processamentos_datahub "
        "DROP CONSTRAINT processamentos_datahub_arquivo_key"
    )
    op.execute(
        "ALTER TABLE processamentos_datahub "
        "ADD CONSTRAINT processamentos_datahub_item_unico UNIQUE (item_id)"
    )
    op.execute("ALTER TABLE processamentos_datahub ADD COLUMN caminho TEXT")
    op.execute("ALTER TABLE processamentos_datahub ADD COLUMN unidade TEXT")

    op.execute(
        f"""
        UPDATE depara_armazem
        SET armazem_na_fonte = '{_UNIDADE_LEGADA}/' || armazem_na_fonte
        WHERE conector_id = (SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub')
          AND armazem_na_fonte IN {_CODIGOS_SEMEADOS}
        """
    )
    op.execute(
        """
        DELETE FROM depara_pendencias
        WHERE conector_id = (SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub')
          AND armazem_na_fonte NOT LIKE '%/%'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE depara_armazem
        SET armazem_na_fonte = replace(armazem_na_fonte, '{_UNIDADE_LEGADA}/', '')
        WHERE conector_id = (SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub')
          AND armazem_na_fonte LIKE '{_UNIDADE_LEGADA}/%'
        """
    )
    op.execute(
        """
        DELETE FROM depara_pendencias
        WHERE conector_id = (SELECT id FROM conectores WHERE tipo = 'sharepoint_datahub')
          AND armazem_na_fonte LIKE '%/%'
        """
    )

    # Destrutivo para o dado novo (mesma politica declarada do 0006): homonimos
    # de unidades diferentes sao legitimos daqui em diante e nao cabem na
    # UNIQUE(arquivo) antiga -- fica o registro de maior id por nome. Na VM o
    # caminho de volta e o pg_dump, nunca este downgrade.
    op.execute(
        """
        DELETE FROM processamentos_datahub p
        WHERE EXISTS (
            SELECT 1 FROM processamentos_datahub outro
            WHERE outro.arquivo = p.arquivo AND outro.id > p.id
        )
        """
    )
    op.execute("ALTER TABLE processamentos_datahub DROP COLUMN IF EXISTS unidade")
    op.execute("ALTER TABLE processamentos_datahub DROP COLUMN IF EXISTS caminho")
    op.execute(
        "ALTER TABLE processamentos_datahub "
        "DROP CONSTRAINT IF EXISTS processamentos_datahub_item_unico"
    )
    op.execute(
        "ALTER TABLE processamentos_datahub "
        "ADD CONSTRAINT processamentos_datahub_arquivo_key UNIQUE (arquivo)"
    )
