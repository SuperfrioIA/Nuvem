"""Corrige o de-para de RMSPII/015 e RMSPII/016 (lote de correcao, 18/ago/2026).

## O que muda (e o que NAO muda)

Desde 30/jul/2026 (`memory/filiais-catering-poc.md`) o projeto tratava `015` e
`016` com sigla propria -- `RMSPIII` e `RMSPIV`.

O cadastro Protheus real (print conferido em 18/ago/2026) confirma que `015` e
`016` TEM codigo e CNPJ proprios -- `008002`/`...0002-68` e `008003`/
`...0003-49` -- **isso nao mudou e nunca foi o erro**. A correcao e outra: a
Maria decidiu que, na exibicao do projeto, as tres (`001`/`015`/`016`) sao
**consideradas RMSPII**, replicando a visao da controladoria que ja estava
registrada (mas nao aplicada) desde 30/jul/2026. `RMSPIII` e `RMSPIV`
continuam existindo como armazens de pleno direito (RMSPIII tem uso real em
ocupacao/capacidade, FK_FILIAL=46) -- so deixam de ser o destino do de-para de
`015`/`016` na ingestao do DataHub.

(Uma tentativa anterior, no mesmo dia, tinha justificado essa migration
dizendo que 015/016 "sao Protheus 008001" -- **isso estava errado**, veio de
uma leitura equivocada de uma tabela digitada a mao. O de-para que a migration
aplica continua correto; so a razao documentada foi corrigida.)

Nao muda nenhum total ja reconciliado: a agregacao "RMSPII" do Power BI sempre
somou 001+015+016 juntos (`docs/CONCILIACAO_POWERBI_V2.md` secao 1). Muda so a
sigla exibida por tras da 015 e da 016 -- o rotulo `016 - RMSPIV` vira
`016 - RMSPII`.

## Contexto: extracao do Luciano (mesmo dia)

Uma extracao independente do DW feita pelo Luciano no mesmo dia
(`volumetriaLucios.csv`, tabela FATO_VOL_REC_CAT) mostra `015` **e** `016`
vindo com CNPJ `06975242000268` (o CNPJ real da RMSPIII/`015`) -- bate pra
`015`, mas nao explica por que `016` aparece la tambem em vez do seu proprio
`...0003-49`. Nao contradiz a decisao de negocio desta migration (que e sobre
como o Nuvem IA EXIBE as tres, nao sobre qual CNPJ o DW usa por baixo); fica
como pendencia de investigacao a parte. Ver `memory/depara-filial-rmspii-dw.md`
e `memory/volumetria-lucios-checagem.md`.

## Por que migration, nao so o seed

`backend/seed_datahub.py` e insert-only (`ON CONFLICT DO NOTHING`), entao
corrigir `filiais_datahub.SIGLA_POR_CODIGO` nao alcanca banco que ja tem as
linhas -- mesmo motivo das migrations 0009 e 0012.

Revision ID: 0018_corrige_sigla_rmspii
Revises: 0017_layout_lido
"""

from alembic import op

revision = "0018_corrige_sigla_rmspii"
down_revision = "0017_layout_lido"
branch_labels = None
depends_on = None

# (codigo de origem qualificado, sigla antiga, sigla corrigida)
CORRECOES = (
    ("RMSPII/015", "RMSPIII", "RMSPII"),
    ("RMSPII/016", "RMSPIV", "RMSPII"),
)


def upgrade() -> None:
    for codigo, _sigla_antiga, sigla_nova in CORRECOES:
        op.execute(
            f"""
            UPDATE depara_armazem d
            SET armazem_id = a.id
            FROM conectores c, armazens a
            WHERE d.conector_id = c.id
              AND c.tipo = 'sharepoint_datahub'
              AND d.armazem_na_fonte = '{codigo}'
              AND a.sigla = '{sigla_nova}'
            """
        )


def downgrade() -> None:
    for codigo, sigla_antiga, _sigla_nova in CORRECOES:
        op.execute(
            f"""
            UPDATE depara_armazem d
            SET armazem_id = a.id
            FROM conectores c, armazens a
            WHERE d.conector_id = c.id
              AND c.tipo = 'sharepoint_datahub'
              AND d.armazem_na_fonte = '{codigo}'
              AND a.sigla = '{sigla_antiga}'
            """
        )
