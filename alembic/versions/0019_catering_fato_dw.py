"""V3.0 -- schema do catering lendo o DW Oracle: dois fatos, tres dimensoes de
decisao e o registro de carga.

## O que muda

Cria seis tabelas novas, todas com prefixo `cat_`. **Nao toca em nada da V1/V2**
-- as 25 tabelas existentes seguem intactas e a V2 continua rodando em producao
enquanto a V3 e construida. Por isso a cadeia de migration continua aqui em vez
de comecar banco novo: a VM ja tem banco, pool e backup configurados, e criar
outro nao traria ganho nenhum.

## Por que dois fatos e nao um

`FATO_VOL_REC_CAT` tem 6 medidas; `FATO_VOL_EXP_CAT` tem 16 (pedido + 3 faixas
x 5). Num fato unico, ~10 colunas ficariam eternamente vazias -- pallet, por
exemplo, nao existe em nenhuma das tres faixas da expedicao. Espelhar as duas
tabelas separadas mantem a invariante que torna a carga auditavel: **uma linha
aqui e uma linha la**. A visao conjunta da Matriz sai de consulta com
`UNION ALL` -- barato com ~120 mil linhas por ano, e nao foi criada aqui porque
o formato exato dela e do V3.2.

## Identidade: a chave natural, nao a PK do DW

`PK_FATO_VOL_*_CAT` vem 1..N sem buraco, com N igual a contagem de linhas, e
TODAS as linhas medidas tem `DW_DATA_INCLUSAO` em 20-21/ago/2026 -- as duas
tabelas foram criadas inteiras naquele dia, e nao ha evidencia de como o
processo se comporta ao longo do tempo. Se ele reconstruir a tabela, a PK deixa
de ser identidade.

Por isso a PK do DW entra como `pk_dw`, coluna de procedencia, e a identidade e
a chave natural
`(nk_instancia, nk_wms_filial, num_gem, nome_estoque, descr_oper_wms,
nk_cliente)` -- unica em 36.300/36.300 e 42.468/42.468 linhas medidas. O UNIQUE
existe tambem como alarme: se a fonte passar a repetir essa combinacao, a carga
falha alto em vez de duplicar em silencio.

## Duas datas, de proposito

`nk_calendario` (a data do calendario do fato, que o BI agrega) e `data_solic`
(quando a guia foi solicitada) divergem em 11,5% das linhas do recebimento e em
62,4% das da expedicao. As duas ficam guardadas: o artefato agrega por
`data_solic`, e medido contra o `fato.csv` o `nk_calendario` encaixa melhor na
expedicao (RMSPII jan-jun -0,32% contra -0,60%). Qual e o padrao da tela e a
decisao A-5 do `V3_PLANO.md`, ainda aberta -- e o schema nao precisa dela para
existir.

## Sem FK do fato para as dimensoes

Deliberado. As tres tabelas de dimensao guardam decisoes NOSSAS (sigla exibida,
razao social canonizada, tipo de estoque) e sao juntadas na leitura. Com FK,
unidade nova ou nome de estoque novo derrubaria a carga e exigiria a maquinaria
de pendencia da V2 -- que existia porque a fonte era planilha suja. Aqui o
padrao e identidade (a sigla que o DW mandou) e `NAO_CLASSIFICADO` e visivel na
tela, que e o sinal.

## Indice

Um por fato, `(nk_calendario, nk_wms_filial)`: serve o filtro so de periodo (a
Matriz pagina todas as unidades) e tambem periodo+unidade. Nao criei indice de
`dw_data_alteracao` porque quem filtra por ela e o Oracle, no lado de la; do
nosso lado so precisamos do maximo, que fica em `cat_cargas`. Indice que nao
serve consulta nenhuma custa escrita e engana quem le o schema -- mesma
disciplina do V2.1.

Revision ID: 0019_catering_fato_dw
Revises: 0018_corrige_sigla_rmspii
"""

from alembic import op

revision = "0019_catering_fato_dw"
down_revision = "0018_corrige_sigla_rmspii"
branch_labels = None
depends_on = None

TABELAS = (
    "cat_fato_expedicao",
    "cat_fato_recebimento",
    "cat_cargas",
    "cat_tipos_estoque",
    "cat_clientes",
    "cat_unidades",
)

# Procedencia + dimensoes: identico nos dois fatos. Mantido como texto unico
# para que as duas tabelas nao possam divergir por descuido de edicao.
_COMUM = """
    id                BIGSERIAL PRIMARY KEY,
    carga_id          INTEGER NOT NULL REFERENCES cat_cargas(id),

    -- procedencia do DW (pk_dw NAO e identidade: ver docstring)
    pk_dw             INTEGER NOT NULL,
    dw_processo       TEXT NOT NULL,
    dw_data_inclusao  TIMESTAMP NOT NULL,
    dw_data_alteracao TIMESTAMP NOT NULL,
    sk_calendario     INTEGER NOT NULL,
    sk_instancia      INTEGER NOT NULL,
    sk_empresa        INTEGER NOT NULL,
    sk_filial         INTEGER NOT NULL,
    sk_cliente        INTEGER NOT NULL,

    -- dimensoes, como o DW manda. Identificador com zero a esquerda e TEXT:
    -- num_gem '0000000001', nk_filial '02060862000569', nk_cliente '01838723',
    -- nk_slin_empresa/filial '001'. Como numero perderiam o zero.
    nk_calendario     DATE NOT NULL,
    nk_instancia      TEXT NOT NULL,
    nk_empresa        TEXT NOT NULL,
    nk_filial         TEXT NOT NULL,
    nk_wms_filial     TEXT NOT NULL,
    nk_qls_filial     TEXT NOT NULL,
    nk_slin_empresa   TEXT NOT NULL,
    nk_slin_filial    TEXT NOT NULL,
    nk_cliente        TEXT NOT NULL,
    nk_wms_cliente    TEXT NOT NULL,
    data_solic        DATE NOT NULL,
    ano_solic         SMALLINT NOT NULL,
    -- 0% vazio no medido, mas nulavel de proposito: guia cancelada nao tem
    -- confirmacao, e o dia que ela entrar na fonte nao pode derrubar a carga.
    dthr_confirm      TIMESTAMP,
    nome_und          TEXT NOT NULL,
    num_gem           TEXT NOT NULL,
    cnpj_cpf_cli      TEXT NOT NULL,
    raz_social        TEXT NOT NULL,
    descr_oper_wms    TEXT NOT NULL,
    nome_estoque      TEXT NOT NULL,
    status_processo   TEXT NOT NULL,
    flg_interface     TEXT NOT NULL,
"""

# NUMERIC(18,3) em peso e valor: o maior medido e 4.751.030,9 com 3 decimais.
_MEDIDAS_REC = """
    qtde_sku          INTEGER,
    qtde_pallet       INTEGER,
    qtde_vol2         INTEGER,
    qtde_peso2        NUMERIC(18,3),
    qtde_pbrt2        NUMERIC(18,3),
    qtde_vlr          NUMERIC(18,3),
"""

_MEDIDAS_EXP = """
    qtde_pedido            INTEGER,
    qtde_sku_solicitado    INTEGER,
    qtde_vol_solicitado    INTEGER,
    qtde_peso_solicitado   NUMERIC(18,3),
    qtde_pbrt_solicitado   NUMERIC(18,3),
    qtde_vlr_solicitado    NUMERIC(18,3),
    qtde_sku_atendido      INTEGER,
    qtde_vol_atendido      INTEGER,
    qtde_peso_atendido     NUMERIC(18,3),
    qtde_pbrt_atendido     NUMERIC(18,3),
    qtde_vlr_atendido      NUMERIC(18,3),
    qtde_sku_separado      INTEGER,
    qtde_vol_separado      INTEGER,
    qtde_peso_separado     NUMERIC(18,3),
    qtde_pbrt_separado     NUMERIC(18,3),
    qtde_vlr_separado      NUMERIC(18,3),
"""

# A identidade. Tambem alarme: se a fonte repetir a combinacao, a carga falha
# alto em vez de duplicar em silencio.
_CHAVE_NATURAL = """
    UNIQUE (nk_instancia, nk_wms_filial, num_gem, nome_estoque,
            descr_oper_wms, nk_cliente)
"""


def upgrade() -> None:
    # ---------------------------------------------- dimensoes de decisao
    # Guardam o que decidimos, nao o que o DW manda -- o fato guarda o do DW.
    # Sem FK vindo do fato: ver docstring.
    op.execute(
        """
        CREATE TABLE cat_unidades (
            sigla_fonte  TEXT PRIMARY KEY,
            sigla        TEXT NOT NULL,
            nome_und     TEXT NOT NULL,
            visto_em     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE cat_clientes (
            raiz_cnpj     TEXT PRIMARY KEY,
            razao_social  TEXT NOT NULL,
            grafias       JSONB NOT NULL DEFAULT '[]',
            visto_em      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE cat_tipos_estoque (
            nome_estoque  TEXT PRIMARY KEY,
            tipo          TEXT NOT NULL,
            regra         TEXT NOT NULL DEFAULT '',
            visto_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
            -- RESFRIADO e classe NOVA, decidida pela Maria em 24/ago/2026: o DW
            -- traz `RESFRIADO - PR` e ela nao existia nas quatro do V2.2.
            CONSTRAINT ck_cat_tipo CHECK (tipo IN
                ('CONGELADO', 'SECO', 'HORTIFRUTI', 'UTENSILIOS', 'RESFRIADO',
                 'NAO_CLASSIFICADO'))
        )
        """
    )

    # ------------------------------------------------- registro de carga
    # `max_dw_data_alteracao` e de onde o incremento retoma. `janela_*` guarda
    # o recorte pedido ao Oracle, porque a carga tambem relê uma janela para
    # pegar linha alterada -- o DW insere e altera (Maria, 24/ago/2026).
    op.execute(
        """
        CREATE TABLE cat_cargas (
            id                    SERIAL PRIMARY KEY,
            tabela_origem         TEXT NOT NULL,
            iniciada_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
            terminada_em          TIMESTAMPTZ,
            status                TEXT NOT NULL DEFAULT 'rodando',
            linhas_lidas          INTEGER NOT NULL DEFAULT 0,
            linhas_inseridas      INTEGER NOT NULL DEFAULT 0,
            linhas_atualizadas    INTEGER NOT NULL DEFAULT 0,
            max_dw_data_alteracao TIMESTAMP,
            janela_de             DATE,
            janela_ate            DATE,
            erro                  TEXT,
            CONSTRAINT ck_cat_carga_status CHECK (status IN
                ('rodando', 'ok', 'erro', 'sem_dado'))
        )
        """
    )

    # -------------------------------------------------------- os dois fatos
    op.execute("CREATE TABLE cat_fato_recebimento (" + _COMUM + _MEDIDAS_REC + _CHAVE_NATURAL + ")")
    op.execute("CREATE TABLE cat_fato_expedicao (" + _COMUM + _MEDIDAS_EXP + _CHAVE_NATURAL + ")")

    # Um indice por fato, e so. O UNIQUE da chave natural ja serve o upsert.
    for tabela, apelido in (("cat_fato_recebimento", "rec"), ("cat_fato_expedicao", "exp")):
        op.execute(
            f"CREATE INDEX ix_cat_fato_{apelido}_periodo "
            f"ON {tabela} (nk_calendario, nk_wms_filial)"
        )


def downgrade() -> None:
    for tabela in TABELAS:
        op.execute(f"DROP TABLE {tabela}")
