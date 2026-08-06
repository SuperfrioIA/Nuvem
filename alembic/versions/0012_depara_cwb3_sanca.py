"""De-para do DataHub para CWB3 e SANCA + indices em `medidas` (lote V2.1).

Duas coisas, as duas de cobertura: destravar metade dos arquivos que estavam
parados em pendencia de de-para, e indexar a tabela que o Cockpit consulta.

## De-para (cadastro, nao schema)

`CWB3/001 -> CWBIII` e `SANCA/025 -> RMSPV`, sob o conector sharepoint_datahub.
As duas siglas ja existem e estao ativas no seed_depara (linhas 97 e 136).

Entra como migration pelo mesmo motivo do 0009_cadastro_filiais: o
backend/seed_datahub.py e insert-only de proposito (`ON CONFLICT DO NOTHING`,
pra nunca sobrescrever ajuste manual do admin), entao corrigir o seed nao muda
banco que ja tenha as linhas. Sem isto, as pendencias antigas de
`depara_pendencias` continuariam penduradas no painel mesmo depois de o de-para
existir -- que e como o `ativo` das filiais ficou como passo manual esquecido
por quatro dias em 30/jul-03/ago. Migration nao esquece.

`RJ/004-003 -> RMRJ` **NAO entra**, apesar de estar na lista da
docs/proposta_v3_volumetria.md secao 4.2. Conferido no dado em 06/ago/2026
(somente leitura, arquivo por arquivo): a `ENTRADA_MERCADORIAS` da RJ tem **18
colunas**, sem `Cliente` e `Cliente CNPJ`, e o leitor atual exige as 20. Dar
de-para pra RJ agora tiraria os 8 arquivos dela (2601-2608) de "pendencia
limpa" e os colocaria em erro de leitura -- trocaria um problema por outro. A RJ
entra no V2.3, com o leitor da variante. `RMSPII/002`, `RJ/004-001` e
`RJ/005-001` seguem fora por decisao da Maria de 02/ago/2026.

Em banco novo isto e no-op duas vezes: migrations rodam ANTES dos seeds, entao
o conector sharepoint_datahub ainda nao existe e o INSERT ... SELECT nao casa
nada; e o seed corrigido ja nasce com as duas linhas.

**O downgrade sozinho nao desfaz o de-para** -- o seed_datahub le o mesmo
`SIGLA_POR_CODIGO`, entao no boot seguinte ele reinsere as duas linhas (e a
pendencia apagada nao volta). Rollback deste lote e rollback de CODIGO, nao de
banco. Vale pra 0009 tambem, e nao ha o que fazer a respeito enquanto o seed
tiver a mesma fonte de verdade da migration -- o que e o desenho correto: uma
fonte unica, dois caminhos de aplicacao (banco novo pelo seed, banco existente
pela migration).

## Indices em `medidas`

Nao havia **nenhum** indice sobre `medidas` em 11 migrations -- o unico servindo
os `WHERE metrica_id = %s` do Cockpit era o da UNIQUE `medidas_celula_unica`
(0006), que e `(metrica_id, armazem_id, competencia, cliente_id)`.

Entram os dois que de fato faltam:

- `(metrica_id, competencia)` -- consulta por periodo sem filtro de armazem;
  hoje `competencia` e a 3a coluna da UNIQUE.
- `(metrica_id, cliente_id, competencia)` -- `cliente_id` e a **4a** coluna da
  UNIQUE, entao ela nao serve a filtro de cliente.

O `(metrica_id, armazem_id, competencia)` da lista da proposta (secao 5, V2.1)
**nao e criado de proposito**: e exatamente o prefixo do indice da UNIQUE, que
ja o atende. Criar custaria escrita e disco e enganaria quem lesse depois.

Revision ID: 0012_depara_cwb3_sanca
Revises: 0011_auditoria
"""

from alembic import op

revision = "0012_depara_cwb3_sanca"
down_revision = "0011_auditoria"
branch_labels = None
depends_on = None

# (codigo de origem qualificado, sigla do armazem) -- espelha as linhas novas de
# backend/services/filiais_datahub.SIGLA_POR_CODIGO
DEPARA_NOVO = (
    ("CWB3/001", "CWBIII"),
    ("SANCA/025", "RMSPV"),
)


def upgrade() -> None:
    for codigo, sigla in DEPARA_NOVO:
        op.execute(
            f"""
            INSERT INTO depara_armazem (conector_id, armazem_na_fonte, armazem_id)
            SELECT c.id, '{codigo}', a.id
            FROM conectores c, armazens a
            WHERE c.tipo = 'sharepoint_datahub' AND a.sigla = '{sigla}'
            ON CONFLICT (conector_id, armazem_na_fonte) DO NOTHING
            """
        )
        # pendencia resolvida deixa de aparecer no painel. Escopo estreito: so a
        # origem que acabou de ganhar de-para, e so no conector do DataHub.
        op.execute(
            f"""
            DELETE FROM depara_pendencias p
            USING conectores c
            WHERE c.id = p.conector_id
              AND c.tipo = 'sharepoint_datahub'
              AND p.armazem_na_fonte = '{codigo}'
            """
        )

    op.execute("CREATE INDEX ix_medidas_metrica_competencia ON medidas (metrica_id, competencia)")
    op.execute(
        "CREATE INDEX ix_medidas_metrica_cliente_competencia "
        "ON medidas (metrica_id, cliente_id, competencia)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_medidas_metrica_cliente_competencia")
    op.execute("DROP INDEX IF EXISTS ix_medidas_metrica_competencia")

    # A pendencia apagada no upgrade NAO e recriada: ela e derivada -- volta
    # sozinha na proxima rodada de processamento se a origem seguir sem de-para.
    # Recriar aqui inventaria um `primeira_vez_em` que nunca existiu.
    for codigo, sigla in DEPARA_NOVO:
        op.execute(
            f"""
            DELETE FROM depara_armazem d
            USING conectores c, armazens a
            WHERE c.id = d.conector_id AND a.id = d.armazem_id
              AND c.tipo = 'sharepoint_datahub'
              AND d.armazem_na_fonte = '{codigo}'
              AND a.sigla = '{sigla}'
            """
        )
