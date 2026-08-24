"""Contrato de colunas das duas tabelas do DW -- MEDIDO, nao suposto.

Fonte da medicao: as extracoes de 21/ago/2026 em `docs/Analise/`
(`dm_volumetriaRecebimento.csv`, 36.300 linhas; `dm_volumetriaExpedicao.csv`,
42.468 linhas), processo `catering_to_dw_volumetry_v01`. A Maria confirmou em
24/ago/2026 que as extracoes sao a **tabela inteira**, sem filtro.

Este modulo existe para que o carregador (V3.1) e o schema (V3.0) partam do
mesmo contrato, e para que um teste possa reprovar a chegada de uma coluna
nova ou a mudanca de tipo antes do dado entrar no banco.

## Nomes

O nome da nossa coluna e o nome do DW em minusculas, com **uma** excecao:
`pk_dw`, que no DW se chama `PK_FATO_VOL_REC_CAT` / `PK_FATO_VOL_EXP_CAT` --
renomeada porque as duas tabelas viram o mesmo formato do nosso lado. Fora
dela a regra vale como invariante testada, e e o que permite o carregador
mapear sem tabela de traducao. Ver `coluna_dw()`.

## Achados da medicao que mudaram o desenho

1. **`PK_FATO_VOL_*_CAT` nao e identidade estavel.** Ela vem 1..N sem buraco,
   e o N e exatamente a contagem de linhas; e TODAS as linhas tem
   `DW_DATA_INCLUSAO` em 20 ou 21/ago/2026 -- ou seja, as duas tabelas foram
   criadas inteiras naquele dia. Nao ha evidencia de como o processo se
   comporta ao longo do tempo. Guardamos a PK como procedencia, mas a
   identidade e a CHAVE_NATURAL abaixo.

2. **Identificador com zero a esquerda e TEXTO, nunca numero.** `NUM_GEM` vem
   como `'0000000001'`, `NK_FILIAL` como `'02060862000569'`, `NK_CLIENTE` como
   `'01838723'`, `NK_SLIN_EMPRESA`/`NK_SLIN_FILIAL` como `'001'`. Convertidos
   para inteiro, perdem o zero e deixam de casar com a fonte. Ver
   `IDENTIFICADORES_TEXTO`.

3. **Existem DUAS datas e elas divergem.** `NK_CALENDARIO` (a data do
   calendario do fato, que o BI agrega) e `DATA_SOLIC` (quando a guia foi
   solicitada). Diferem em 11,5% das linhas do recebimento e em **62,4%** das
   da expedicao. No total do mes a diferenca e pequena (<=1,2% de jan a jul),
   mas nas bordas do periodo e grande. Medido contra o `fato.csv`
   (FATO_VOLUMETRIA, o que o Power BI consome), `NK_CALENDARIO` encaixa
   melhor na expedicao: RMSPII jan-jun -0,32% por calendario contra -0,60%
   por solicitacao, e junho -2,48% contra -5,44%. O artefato usa `DATA_SOLIC`
   -- decisao A-5 do `V3_PLANO.md`, aberta. O schema guarda as duas.
"""

# --------------------------------------------------------------- tabelas
TABELA_REC = "FATO_VOL_REC_CAT"
TABELA_EXP = "FATO_VOL_EXP_CAT"
PROCESSO_DW = "catering_to_dw_volumetry_v01"

# Escopo do negocio (Maria, 24/ago/2026): catering = instancias SLIN. As
# outras instancias do DW (DISTROMAQ_PRD, MDLZ_PRD, DISTRO_PRD, SEEDS_PRD,
# ATIVA_*) sao outro negocio e ficam FORA -- nao e dado faltando.
PREFIXO_INSTANCIA = "SLIN_"

# ------------------------------------------------------------ identidade
# Unica em 36.300/36.300 e 42.468/42.468 linhas medidas. Menos que isto NAO
# serve: sem `nk_cliente` sobra 1 duplicata no recebimento e 65 na expedicao;
# sem `descr_oper_wms` sobram 202 e 93; so (instancia, filial, gem) repete ate
# 3 vezes -- e o grao de tipo de estoque dentro da guia.
CHAVE_NATURAL = (
    "nk_instancia",
    "nk_wms_filial",
    "num_gem",
    "nome_estoque",
    "descr_oper_wms",
    "nk_cliente",
)

# Identificador: texto sempre, porque tem zero a esquerda significativo.
IDENTIFICADORES_TEXTO = frozenset({
    "num_gem",
    "nk_filial",
    "nk_cliente",
    "cnpj_cpf_cli",
    "nk_slin_empresa",
    "nk_slin_filial",
})

# O armazem dentro da unidade NAO e a filial sozinha: `001/001` aparece em
# duas unidades (Barueri e Curitiba) e separa so pela instancia; e o CNPJ nao
# separa 015 de 016 (os dois vem 06975242000268). Medido no artefato,
# 21/ago/2026 -- ver memory/depara-filial-rmspii-dw.md.
CHAVE_ARMAZEM = ("nk_instancia", "nk_slin_empresa", "nk_slin_filial")

# --------------------------------------------------------------- colunas
# (nome, tipo SQL, aceita nulo). Tipo medido no dado, nao inferido do nome.
PROCEDENCIA = (
    ("pk_dw", "INTEGER", False),            # PK_FATO_VOL_*_CAT: procedencia, nao identidade
    ("dw_processo", "TEXT", False),
    ("dw_data_inclusao", "TIMESTAMP", False),
    ("dw_data_alteracao", "TIMESTAMP", False),
    ("sk_calendario", "INTEGER", False),
    ("sk_instancia", "INTEGER", False),
    ("sk_empresa", "INTEGER", False),
    ("sk_filial", "INTEGER", False),
    ("sk_cliente", "INTEGER", False),
)

DIMENSOES = (
    ("nk_calendario", "DATE", False),
    ("nk_instancia", "TEXT", False),
    ("nk_empresa", "TEXT", False),
    ("nk_filial", "TEXT", False),
    ("nk_wms_filial", "TEXT", False),
    ("nk_qls_filial", "TEXT", False),
    ("nk_slin_empresa", "TEXT", False),
    ("nk_slin_filial", "TEXT", False),
    ("nk_cliente", "TEXT", False),
    ("nk_wms_cliente", "TEXT", False),
    ("data_solic", "DATE", False),
    ("ano_solic", "SMALLINT", False),
    # 0% vazio no medido, mas nulavel de proposito: guia de recebimento
    # cancelada nao tem confirmacao, e o dia que ela entrar na fonte nao pode
    # derrubar a carga. Ver "limitacoes herdadas" no V3_PLANO.
    ("dthr_confirm", "TIMESTAMP", True),
    ("nome_und", "TEXT", False),
    ("num_gem", "TEXT", False),
    ("cnpj_cpf_cli", "TEXT", False),
    ("raz_social", "TEXT", False),
    ("descr_oper_wms", "TEXT", False),
    ("nome_estoque", "TEXT", False),
    ("status_processo", "TEXT", False),
    ("flg_interface", "TEXT", False),
)

# NUMERIC(18,3) em toda medida de peso e valor: o maior medido e 4.751.030,9
# com 3 decimais, e padronizar evita que o proximo mes estoure a precisao.
_PESO = "NUMERIC(18,3)"

MEDIDAS_REC = (
    ("qtde_sku", "INTEGER", True),
    ("qtde_pallet", "INTEGER", True),
    ("qtde_vol2", "INTEGER", True),
    ("qtde_peso2", _PESO, True),
    ("qtde_pbrt2", _PESO, True),
    ("qtde_vlr", _PESO, True),
)

MEDIDAS_EXP = (
    ("qtde_pedido", "INTEGER", True),
    ("qtde_sku_solicitado", "INTEGER", True),
    ("qtde_vol_solicitado", "INTEGER", True),
    ("qtde_peso_solicitado", _PESO, True),
    ("qtde_pbrt_solicitado", _PESO, True),
    ("qtde_vlr_solicitado", _PESO, True),
    ("qtde_sku_atendido", "INTEGER", True),
    ("qtde_vol_atendido", "INTEGER", True),
    ("qtde_peso_atendido", _PESO, True),
    ("qtde_pbrt_atendido", _PESO, True),
    ("qtde_vlr_atendido", _PESO, True),
    ("qtde_sku_separado", "INTEGER", True),
    ("qtde_vol_separado", "INTEGER", True),
    ("qtde_peso_separado", _PESO, True),
    ("qtde_pbrt_separado", _PESO, True),
    ("qtde_vlr_separado", _PESO, True),
)

COLUNAS_REC = PROCEDENCIA + DIMENSOES + MEDIDAS_REC
COLUNAS_EXP = PROCEDENCIA + DIMENSOES + MEDIDAS_EXP

# ------------------------------------------------------- leitura da tela
# As 5 lentes do artefato. `pallet` so existe na ENTRADA -- nenhuma das tres
# faixas da expedicao tem medida de pallet. Nao e defeito, e a fonte.
LENTES = {
    "liq": {"nome": "Peso liquido", "unidade": "t", "rec": "qtde_peso2", "exp": "peso"},
    "bru": {"nome": "Peso bruto", "unidade": "t", "rec": "qtde_pbrt2", "exp": "pbrt"},
    "pal": {"nome": "Pallets", "unidade": "UA", "rec": "qtde_pallet", "exp": None},
    "vol": {"nome": "Volumes", "unidade": "cx", "rec": "qtde_vol2", "exp": "vol"},
    "val": {"nome": "Valor", "unidade": "R$", "rec": "qtde_vlr", "exp": "vlr"},
}

# As 3 faixas da expedicao. Cancelada tem peso no SOLICITADO e 0,0 no
# atendido e no separado (medido: 974 linhas, 4.530,9 t liquidas).
FAIXAS = ("solicitado", "atendido", "separado")


def coluna_exp(lente: str, faixa: str):
    """Nome da coluna da expedicao para uma lente numa faixa. None quando a
    medida nao existe naquele lado (o caso do pallet)."""
    if lente not in LENTES:
        raise KeyError(lente)
    if faixa not in FAIXAS:
        raise KeyError(faixa)
    sufixo = LENTES[lente]["exp"]
    return None if sufixo is None else f"qtde_{sufixo}_{faixa}"


MOVIMENTOS = ("rec", "exp")

# A unica coluna cujo nome nosso NAO e o do DW em minusculas.
RENOMEADAS = {
    "pk_dw": {"rec": "PK_" + TABELA_REC, "exp": "PK_" + TABELA_EXP},
}


def coluna_dw(nossa: str, movimento: str) -> str:
    """Nome da coluna no DW. Invariante: e a nossa em maiusculas, exceto o que
    estiver em RENOMEADAS."""
    if movimento not in MOVIMENTOS:
        raise KeyError(movimento)
    if nossa in RENOMEADAS:
        return RENOMEADAS[nossa][movimento]
    return nossa.upper()


def colunas(movimento: str):
    """Colunas do fato de um movimento, na ordem do schema."""
    if movimento == "rec":
        return COLUNAS_REC
    if movimento == "exp":
        return COLUNAS_EXP
    raise KeyError(movimento)
