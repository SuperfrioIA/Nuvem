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

O nome do OBJETO e outra coisa, e ele mudou no V3.5: e
`DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`, qualificado, vindo de `tabela()` -- que
le configuracao. O nome da coluna da PK **nao** deriva dele (ver `PK_DW`): a
tabela ganhou schema e sufixo de versao, a coluna nao.

## Achados da medicao que mudaram o desenho

1. **`PK_FATO_VOL_*_CAT` nao e identidade estavel.** Ela vem 1..N sem buraco,
   e o N e exatamente a contagem de linhas; e TODAS as linhas tem
   `DW_DATA_INCLUSAO` em 20 ou 21/ago/2026 -- ou seja, as duas tabelas foram
   criadas inteiras naquele dia. Nao ha evidencia de como o processo se
   comporta ao longo do tempo. Guardamos a PK como procedencia, mas a
   identidade e a CHAVE_NATURAL abaixo. Em 25/ago/2026 a tabela FOI
   reconstruida, com 3,6 anos de historico e todo `dw_data_alteracao` novo --
   entao isto deixou de ser precaucao e passou a ser fato observado.

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

import os
import re
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MOVIMENTOS = ("rec", "exp")

# --------------------------------------------------------------- tabelas
# Nome QUALIFICADO, como a sondagem de 25/ago/2026 provou que o objeto se chama
# (`DM_VOLUMETRIA`, e sufixo `_V01`). O nome que o projeto guardava antes --
# `FATO_VOL_REC_CAT`, sem schema e sem sufixo -- e o que levou `ORA-00942` na
# primeira sondagem. `ORA-00942` responde a mesma coisa para "nao existe" e
# para "existe e voce nao pode ver", entao ele nunca prova falta de GRANT
# sozinho.
#
# Os dois valores viram `cat_cargas.tabela_origem`, que e CHAVE da marca
# d'agua (`destino.marca_dagua()` filtra por ela). Qualificar invalida a marca
# d'agua das rodadas anteriores de proposito, e a hora de fazer isso e agora:
# a V3 nunca rodou em producao, entao a recarga custa uma rodada completa
# contra o DW. Depois do V3.6 custaria carga cheia em producao.
TABELA_REC = "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01"
TABELA_EXP = "DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01"
PROCESSO_DW = "catering_to_dw_volumetry_v01"

# O nome da coluna da PK, MEDIDO, e deliberadamente desacoplado do nome da
# tabela. Ele ja foi `"PK_" + TABELA_REC`, e isso funcionava so enquanto os
# dois andavam juntos: a tabela ganhou schema e sufixo de versao, e a coluna
# nao -- concatenar produziria `PK_DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`, que
# nao existe. Derivar um identificador de outro e economia que cobra juros na
# primeira vez que os dois divergem.
PK_DW = {
    "rec": "PK_FATO_VOL_REC_CAT",
    "exp": "PK_FATO_VOL_EXP_CAT",
}

# Variavel de ambiente que troca o nome do objeto sem tocar em codigo. A A-7
# do `V3_PLANO.md` diz que fica so a `_V01` e nao ha outra versao programada --
# mas "nao programada" e ausencia de plano, nao garantia, e a `FATO_VOLUMETRIA`
# do mesmo schema ja esta em `_V04`. Entao o nome vive em configuracao, num
# lugar so.
_ENV_TABELA = {"rec": "DW_TABELA_REC", "exp": "DW_TABELA_EXP"}

# Nome de objeto nao pode ser bind: ele e concatenado no SQL. Entao ele precisa
# de guarda propria -- identificador Oracle em maiuscula, com schema opcional.
_NOME_VALIDO = re.compile(r"^[A-Z][A-Z0-9_$#]*(\.[A-Z][A-Z0-9_$#]*)?$")


class TabelaInvalida(ValueError):
    """Nome de objeto que nao pode entrar num SQL."""


def tabela(movimento: str) -> str:
    """O nome qualificado do objeto no DW, com a configuracao tendo a palavra
    final. Vale para o SELECT do V3.5 e para `cat_cargas.tabela_origem` -- os
    dois tem que dizer o MESMO nome, senao a marca d'agua procura por um nome
    que a carga nunca gravou."""
    if movimento not in MOVIMENTOS:
        raise KeyError(movimento)
    padrao = TABELA_REC if movimento == "rec" else TABELA_EXP
    nome = (os.environ.get(_ENV_TABELA[movimento]) or padrao).strip()
    if not _NOME_VALIDO.match(nome):
        raise TabelaInvalida(
            f"{_ENV_TABELA[movimento]}={nome!r} nao e nome de objeto Oracle "
            "valido (esperado SCHEMA.TABELA em maiusculas)"
        )
    return nome


# Escopo do negocio (Maria, 24/ago/2026): catering = instancias SLIN. As
# outras instancias do DW (DISTROMAQ_PRD, MDLZ_PRD, DISTRO_PRD, SEEDS_PRD,
# ATIVA_*) sao outro negocio e ficam FORA -- nao e dado faltando.
PREFIXO_INSTANCIA = "SLIN_"

# --------------------------------------------------------- piso de periodo
# Escopo de PERIODO (Maria, 25/ago/2026): a V3 le **de 2026 para frente**.
#
# Por que isto existe: em 25/ago o DW reconstruiu as duas tabelas com historico
# desde 02/jan/2023, e elas passaram de 79 mil para 434 mil linhas. Ler 2023-2025
# nao serve a tela de hoje -- e a Maria decidiu o recorte olhando o que a Matriz
# mostra, nao o que a fonte tem.
#
# Fica em **configuracao** e nao como constante enterrada porque a propria Maria
# nomeou o caso de uso: comparar 2025 com 2026 um dia. Trocar para 2025 e uma
# variavel de ambiente, sem commit e sem migration.
#
# Duas coisas que valem saber antes de mexer nele:
#
#   1. o piso corta por **`nk_calendario`**, a data do movimento -- a mesma que a
#      Matriz agrega (A-5). Guia pedida em dez/2025 e movimentada em jan/2026
#      ENTRA, porque ela conta em 2026;
#   2. **baixar o piso carrega o passado; subir o piso nao apaga nada.** A carga
#      so insere e atualiza (decisao do V3.1), entao linha que ja entrou fica.
#      Voltar atras de um piso mais baixo exige DELETE a mao, deliberado.
ANO_MINIMO_PADRAO = 2026
ENV_ANO_MINIMO = "DW_ANO_MINIMO"

# Faixa sa. O que isto pega e o dedo errado -- `20226`, `26`, `2o26` -- que sem
# guarda viraria "carrega tudo" ou "carrega nada" em silencio.
_ANO_MIN, _ANO_MAX = 2000, 2100


class AnoMinimoInvalido(ValueError):
    """Valor de `DW_ANO_MINIMO` que nao e ano."""


def ano_minimo() -> int:
    """O primeiro ano que a carga le, do ambiente ou do padrao."""
    bruto = (os.environ.get(ENV_ANO_MINIMO) or "").strip()
    if not bruto:
        return ANO_MINIMO_PADRAO
    try:
        ano = int(bruto)
    except ValueError:
        raise AnoMinimoInvalido(
            f"{ENV_ANO_MINIMO}={bruto!r} nao e um ano"
        ) from None
    if not _ANO_MIN <= ano <= _ANO_MAX:
        raise AnoMinimoInvalido(
            f"{ENV_ANO_MINIMO}={ano} esta fora de {_ANO_MIN}..{_ANO_MAX}"
        )
    return ano


def piso_do_periodo() -> date:
    """O primeiro dia que a carga le. `date` e nao ano porque e assim que ele
    entra no bind do SQL e na comparacao do CSV -- converter em dois lugares e
    como as duas pontas comecam a divergir."""
    return date(ano_minimo(), 1, 1)


# ------------------------------------------------------- fuso de exibicao
# **O dado nao muda; a leitura dele muda.** `cat_cargas.terminada_em` e
# `cat_auditoria.criado_em` sao `timestamptz` e guardam UTC, que e o certo. O
# defeito estava na exibicao: o `to_char` renderiza no fuso da SESSAO do
# Postgres, que no container e `Etc/UTC` -- entao uma carga das 09h45 aparecia
# como 12h45 na tela, tres horas no futuro.
#
# Medido em 26/ago/2026, no fechamento do V3.5, em dois lugares: o rodape "De
# quando e o dado" e a coluna "quando" da auditoria. O segundo e o que pesa --
# auditoria com hora errada e problema de rastreabilidade, e nao de estetica: e
# o registro que se consulta quando alguem pergunta quem baixou o que, e quando.
#
# Por que configuracao e nao a constante enterrada nos dois SQL: o dia em que a
# exibicao passar a ser no fuso de QUEM LE (ISO-8601 para o front, formatado no
# navegador) e para haver **um** lugar para mexer. Espalhar
# `'America/Sao_Paulo'` por dois `to_char` e garantir que o terceiro nasca
# esquecido.
#
# `max_dw_data_alteracao` NAO entra aqui: ela e `timestamp without time zone`
# de proposito, porque e o relogio do DW e nao o nosso.
FUSO_EXIBICAO_PADRAO = "America/Sao_Paulo"
ENV_FUSO_EXIBICAO = "CAT_FUSO_EXIBICAO"


class FusoInvalido(ValueError):
    """Valor de `CAT_FUSO_EXIBICAO` que o sistema nao conhece."""


def fuso_exibicao() -> str:
    """O fuso em que data e hora aparecem na tela, do ambiente ou do padrao.

    Valida na LEITURA, nao no uso. Fuso escrito errado (`America/SaoPaulo`,
    `BRT`) tem que falhar nomeando a variavel -- a alternativa e o Postgres
    estourar no meio de uma consulta de tela, com uma mensagem que nao aponta
    para a configuracao."""
    nome = (os.environ.get(ENV_FUSO_EXIBICAO) or "").strip()
    if not nome:
        return FUSO_EXIBICAO_PADRAO
    try:
        ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError):
        raise FusoInvalido(
            f"{ENV_FUSO_EXIBICAO}={nome!r} nao e um fuso conhecido "
            f"(esperado no formato de {FUSO_EXIBICAO_PADRAO!r})"
        ) from None
    return nome

# ------------------------------------------------------------ identidade
# Sem `nk_cliente` sobra 1 duplicata no recebimento e 65 na expedicao; sem
# `descr_oper_wms` sobram 202 e 93; so (instancia, filial, gem) repete ate 3
# vezes -- e o grao de tipo de estoque dentro da guia.
#
# **`ano_solic` entrou em 25/ago/2026 (migration 0023), e foi a primeira carga
# real que cobrou.** As seis primeiras colunas foram medidas unicas em
# 36.300/36.300 e 42.468/42.468 linhas -- nos CSVs de 21/ago, que tinham **um
# ano so**. Quando o DW passou a publicar 2023-2026 (201.848 e 231.886 linhas),
# a chave repetiu em 27.834 e 44.187 linhas, porque **`num_gem` se recicla por
# ano**: a mesma guia aparece 4x, uma por ano, em datas proximas dentro do ano.
# Generalizar unicidade de uma amostra de um ano para a serie inteira foi a
# falha -- e o upsert recusou alto, que era o que ele tinha que fazer.
#
# Por que `ano_solic` e nao uma das duas datas (as duas tambem ficariam unicas):
#
#   1. o espaco de numeracao e o ano do PEDIDO, nao o do movimento -- somar o
#      ano de `nk_calendario` NAO fica unico (12 linhas no recebimento, 79 na
#      expedicao: as viradas de ano);
#   2. a identidade certa e a mais GROSSA que ainda seja unica, porque
#      identidade fina transforma correcao em INSERT duplicado;
#   3. `data_solic` tem lixo (`2105-04-29`, `2002-04-29`, `2005-05-07` em 16
#      linhas da expedicao, com `nk_calendario` sao) e `ano_solic` nao. Existe
#      defeito na fonte que alguem vai corrigir, e com a data na chave essa
#      correcao duplicaria a linha em silencio.
#
# `ano_solic` fica depois do `num_gem` porque ele qualifica o numero da guia: a
# chave se le como "o GEM e unico dentro do ano do pedido".
CHAVE_NATURAL = (
    "nk_instancia",
    "nk_wms_filial",
    "num_gem",
    "ano_solic",
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
# `nome` e rotulo de TELA, entao vai acentuado -- diferente do resto do modulo,
# que e ASCII por convencao de codigo. Quem le a tela nao le o codigo.
LENTES = {
    "liq": {"nome": "Peso líquido", "unidade": "t", "rec": "qtde_peso2", "exp": "peso"},
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


# A unica coluna cujo nome nosso NAO e o do DW em minusculas. Ver `PK_DW`:
# nome medido, e nao derivado do nome da tabela.
RENOMEADAS = {
    "pk_dw": PK_DW,
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
