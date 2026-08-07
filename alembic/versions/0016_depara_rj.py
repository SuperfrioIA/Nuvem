"""De-para da RJ: RJ/004-003 -> RMRJ (lote V2.3).

Retido de proposito desde o V2.1 (migration 0012): a `ENTRADA_MERCADORIAS` da
RJ tem 18 colunas, sem `Cliente`/`Cliente CNPJ`, e o leitor da epoca exigia as
20. Dar de-para naquele momento tiraria os 8 arquivos dela (2601-2608) de
"pendencia limpa" e os colocaria em erro de leitura -- trocaria um problema
por outro.

O V2.3 entrega o leitor da variante (backend/services/entrada_mercadorias.py
passa a detectar o layout pelo cabecalho, nao pela unidade), entao o de-para
pode entrar agora. Mesmo padrao da 0012: insere o de-para e apaga a
pendencia correspondente NA MESMA migration -- e a licao de 03/ago (correcao
de cadastro entra como migration, nao como SQL manual no runbook); sem isso
as pendencias antigas de `depara_pendencias` ficariam penduradas no painel
mesmo com o de-para ja existindo.

`RMRJ` ja existe e esta ativa em `backend/seed_depara.py` (mesma fonte das
demais siglas). Decisao D2 do V2.3: sem `Cliente CNPJ`, toda a RMRJ cai no
balde "sem cliente identificado" -- SEM pendencia de cliente (nao ha CNPJ pra
cadastrar; `raiz_cnpj(None)` ja devolve None e o processamento so registra
pendencia quando a raiz nao e None).

Em banco novo isto e no-op: migrations rodam ANTES dos seeds, entao o
conector sharepoint_datahub ainda nao existe quando o INSERT...SELECT roda; e
o seed corrigido (backend/seed_datahub.py, que le
filiais_datahub.SIGLA_POR_CODIGO) ja nasce com a linha.

O downgrade sozinho NAO desfaz o de-para -- mesma ressalva da 0012: o
seed_datahub le o mesmo SIGLA_POR_CODIGO, entao o proximo boot reinsere a
linha. Rollback deste lote e rollback de CODIGO (reverter o commit que tirou
a RJ do comentario em filiais_datahub.py), nao de banco.

Revision ID: 0016_depara_rj
Revises: 0015_metricas_direcionais
"""

from alembic import op

revision = "0016_depara_rj"
down_revision = "0015_metricas_direcionais"
branch_labels = None
depends_on = None

_CODIGO = "RJ/004-003"
_SIGLA = "RMRJ"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
        SELECT c.id, '{_CODIGO}', a.id
        FROM conectores c, armazens a
        WHERE c.tipo = 'sharepoint_datahub' AND a.sigla = '{_SIGLA}'
        ON CONFLICT (conector_id, armazem_na_fonte) DO NOTHING
        """
    )
    op.execute(
        f"""
        DELETE FROM depara_pendencias p
        USING conectores c
        WHERE c.id = p.conector_id
          AND c.tipo = 'sharepoint_datahub'
          AND p.armazem_na_fonte = '{_CODIGO}'
        """
    )


def downgrade() -> None:
    # A pendencia apagada no upgrade NAO e recriada -- ela e derivada e volta
    # sozinha na proxima rodada de processamento se a origem seguir sem
    # de-para (mesmo raciocinio da 0012).
    op.execute(
        f"""
        DELETE FROM depara_armazem d
        USING conectores c, armazens a
        WHERE c.id = d.conector_id AND a.id = d.armazem_id
          AND c.tipo = 'sharepoint_datahub'
          AND d.armazem_na_fonte = '{_CODIGO}'
          AND a.sigla = '{_SIGLA}'
        """
    )
