"""Correcao de cadastro de filiais conferida com a Maria em 03/ago/2026:
CWBI inativa e sem o apelido `001995`, RPIII inativa com CNPJ.

Sao dados de cadastro, nao schema -- entram como migration porque o seed
(backend/seed_depara.py) e insert-only por decisao (`ON CONFLICT DO NOTHING`,
pra nunca sobrescrever ajuste manual do admin). Sem isto, corrigir o seed nao
altera banco nenhum que ja tenha as linhas: foi o que aconteceu com o `ativo`
das filiais RMSPIII/RMSPIV, que ficou como passo manual pendente na VM de
30/jul a 03/ago. Migration nao esquece.

O que muda:

- `CWBI` passa a `ativo = false`. Ela e pre-operacional: nao esta no cadastro
  oficial de filiais ativas, nao tem CNPJ e nao tem volumetria. O unico
  vestigio dela e o cadastro de capacidade do DW (uma camara de congelado).
- o apelido `001995` do de-para e REMOVIDO. Nao e codigo Protheus valido
  (confirmado pela Maria em 03/ago/2026): vinha de uma linha pela metade da
  tabela de de-para do DW -- `ERP PROTHEUS FILIAL = 001995` com
  `WMS JDA WH ID` em branco, cluster "New Stores", criada em 20/11/2020 -- e o
  pareamento com CWBI foi inferencia do Lote 7, nao dado da fonte.
- `RPIII` passa a `ativo = false` e ganha o CNPJ `02060862000640` como apelido.
  Ela NAO e pre-operacional, como o Lote 7 supos: e filial real desativada
  (codigo 001006, Ribeirao Preto/SP, situacao cadastral INATIVO; o DW tem o
  de-para completo dela e a exclui do KPI de ocupacao). O `nome` tambem e
  corrigido -- era o placeholder "RPIII".

`CWBIV` (001034) NAO entra aqui: e sigla nova, entao o proprio seed a insere no
startup seguinte (o `ON CONFLICT` so protege linha existente). Duplicar isso
numa migration criaria duas fontes de verdade pro mesmo cadastro.

Efeito na contagem do runbook (docs/DEPLOY.md, passo 6): 35 armazens semeados,
31 ativos -- inativas sao MRS, RMSPIII, CWBI e RPIII.

Em banco novo isto e no-op: migrations rodam ANTES dos seeds, e o seed corrigido
ja nasce com o estado certo.

Revision ID: 0009_cadastro_filiais
Revises: 0008_identidade_datahub
"""

from alembic import op

revision = "0009_cadastro_filiais"
down_revision = "0008_identidade_datahub"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE armazens SET ativo = false WHERE sigla IN ('CWBI', 'RPIII')")
    op.execute(
        "UPDATE armazens SET nome = 'Ribeirão Preto/SP' "
        "WHERE sigla = 'RPIII' AND nome = 'RPIII'"
    )

    # escopo estreito de proposito: so a linha que aponta 001995 -> CWBI.
    # Um de-para de 001995 pra outro armazem seria cadastro de alguem, nao este
    # residuo, e nao e desta migration apagar.
    op.execute(
        """
        DELETE FROM depara_armazem
        WHERE armazem_na_fonte = '001995'
          AND armazem_id = (SELECT id FROM armazens WHERE sigla = 'CWBI')
        """
    )

    # CNPJ da RPIII como apelido, no mesmo conector em que o seed_depara escreve
    op.execute(
        """
        INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
        SELECT c.id, '02060862000640', a.id
        FROM conectores c, armazens a
        WHERE c.tipo = 'upload_manual' AND a.sigla = 'RPIII'
        ON CONFLICT (conector_id, armazem_na_fonte) DO NOTHING
        """
    )


def downgrade() -> None:
    # Restaura o estado anterior, que era o errado -- e o que downgrade
    # significa. Os INSERT/DELETE sao idempotentes e nao fazem nada se as
    # siglas nao existirem no banco.
    op.execute("UPDATE armazens SET ativo = true WHERE sigla IN ('CWBI', 'RPIII')")
    op.execute(
        "UPDATE armazens SET nome = 'RPIII' "
        "WHERE sigla = 'RPIII' AND nome = 'Ribeirão Preto/SP'"
    )
    op.execute(
        """
        DELETE FROM depara_armazem
        WHERE armazem_na_fonte = '02060862000640'
          AND armazem_id = (SELECT id FROM armazens WHERE sigla = 'RPIII')
        """
    )
    op.execute(
        """
        INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
        SELECT c.id, '001995', a.id
        FROM conectores c, armazens a
        WHERE c.tipo = 'upload_manual' AND a.sigla = 'CWBI'
        ON CONFLICT (conector_id, armazem_na_fonte) DO NOTHING
        """
    )
