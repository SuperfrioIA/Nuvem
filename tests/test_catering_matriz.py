"""V3.2 -- a Matriz, com aceite celula por celula contra os CSVs.

## O aceite deste lote

`test_aceite_celula_por_celula_contra_os_csvs` calcula a Matriz **duas vezes por
caminhos independentes**:

  1. em Python puro, lendo os CSVs de `docs/Analise/` com o modulo `csv`;
  2. pelo SQL de `catering/consulta/matriz.py`, contra o dado carregado.

E compara **cada celula**. Duas implementacoes independentes chegando ao mesmo
numero e a forma mais forte de aceite disponivel aqui -- e substitui o lado a
lado com o artefato, que foi apagado em 24/ago/2026.

O que o caminho de Python **nao** compartilha com o de producao: ele nao importa
`matriz.py`, nao usa o carregador e reimplementa o de-para da sigla como um dict
literal. Se compartilhasse, os dois erros seriam o mesmo erro e o aceite nao
provaria nada.

O de-para `RMSPV -> RMSPIV` aparece literal aqui de proposito: mudar a decisao
do de-para **tem** que quebrar este teste. E decisao de negocio, nao detalhe.

## Por que a comparacao e por CHAVE, nao por rotulo

A celula e identificada por `(sigla, raiz_cnpj, [faixa], operacao, mes)` -- as
chaves. O rotulo do cliente e a razao social canonizada pela grafia de maior
peso, e isso ja tem teste proprio em `test_catering_carga.py`. Misturar as duas
coisas faria uma falha de canonizacao parecer erro de soma.

## Poucos testes de banco

Mesma disciplina do `test_catering_schema.py`: a fixture roda as 20 migrations a
cada teste, e o aceite carrega 78.768 linhas. Cada assert carrega mensagem
propria, entao a falha continua dizendo o que quebrou.
"""

import calendar
import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import psycopg2
import pytest

from catering import contrato
from catering.carga import carregar_tudo
from catering.carga.fonte_csv import FonteCSV
from catering.consulta import matriz, recorte

DIRETORIO_DW = Path(__file__).resolve().parent.parent / "docs" / "Analise"

tem_extracao = pytest.mark.skipif(
    not (DIRETORIO_DW / "dm_volumetriaRecebimento.csv").exists(),
    reason=(
        "docs/Analise/ e gitignored (dado real de operacao nao vai pro Git). "
        "Este teste roda onde a extracao de 21/ago/2026 existe."
    ),
)

# Literal de proposito -- ver docstring. NAO importar de catering.dominio.
SIGLA_EXIBIDA_ESPERADA = {"RMSPV": "RMSPIV"}

ARQUIVO = {
    "rec": "dm_volumetriaRecebimento.csv",
    "exp": "dm_volumetriaExpedicao.csv",
}


# ------------------------------------------------- o caminho independente
def _mes(valor):
    """`2026-01-05 00:00:00.000` -> `2026-01`. Recorta texto de proposito: nao
    usa o parser do carregador."""
    return valor.strip()[:7]


def _numero(valor):
    valor = (valor or "").strip()
    return Decimal(valor) if valor else None


def esperado_do_csv(movimento, lente, de, ate, dias=()):
    """A Matriz calculada em Python puro, direto do CSV.

    Devolve `{(sigla, raiz, faixa_ou_vazio, operacao, mes): valor}` -- as
    celulas das FOLHAS. Os niveis de cima sao somas das folhas, e o teste
    confere isso separadamente.

    `de`/`ate` sao DATAS (`AAAA-MM-DD`) e `dias` e o filtro de dia do mes, como
    no recorte de verdade. O recorte por dia entrou em 26/ago/2026, e o aceite
    subiu junto: antes este caminho comparava mes com mes, o que nao provava
    nada sobre corte no meio do mes."""
    caminho = DIRETORIO_DW / ARQUIVO[movimento]
    if movimento == "rec":
        colunas = {"": contrato.LENTES[lente]["rec"].upper()}
    else:
        colunas = {}
        for faixa in contrato.FAIXAS:
            nome = contrato.coluna_exp(lente, faixa)
            if nome is not None:
                colunas[faixa] = nome.upper()

    celulas = defaultdict(lambda: None)
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo, delimiter=";"):
            # `AAAA-MM-DD` compara lexicograficamente na ordem certa, e o
            # corte e feito no DIA -- e assim que o recorte de verdade corta.
            dia = linha["NK_CALENDARIO"].strip()[:10]
            if not (de <= dia <= ate):
                continue
            if dias and int(dia[8:10]) not in dias:
                continue
            mes = _mes(linha["NK_CALENDARIO"])
            if not linha["NK_INSTANCIA"].startswith("SLIN_"):
                continue
            sigla_fonte = linha["NK_WMS_FILIAL"].strip()
            sigla = SIGLA_EXIBIDA_ESPERADA.get(sigla_fonte, sigla_fonte)
            for faixa, coluna in colunas.items():
                valor = _numero(linha[coluna])
                if valor is None:
                    continue
                # a entrada nao tem nivel de faixa, entao a chave dela e menor
                # -- tem que casar com o caminho da arvore, que tambem nao tem
                nivel_faixa = (faixa,) if faixa else ()
                chave = (
                    (sigla, linha["NK_CLIENTE"].strip())
                    + nivel_faixa
                    + (linha["DESCR_OPER_WMS"].strip(), mes)
                )
                atual = celulas[chave]
                celulas[chave] = valor if atual is None else atual + valor
    return dict(celulas)


# ------------------------------------------------------ achatar a arvore
def _folhas(nos, caminho=()):
    """`{(chave...., mes): valor}` das folhas da arvore devolvida pela Matriz."""
    saida = {}
    for no in nos:
        atual = caminho + (no["chave"],)
        if no["filhos"]:
            saida.update(_folhas(no["filhos"], atual))
        else:
            for mes, valor in no["valores"].items():
                saida[atual + (mes,)] = valor
    return saida


# O recorte passou a ser por DIA (26/ago/2026), e a coluna continua mensal --
# entao teste que fala de mes precisa das duas pontas dele. Calculado, e nao
# escrito a mao, para nao existir um "2026-02-31" em teste nenhum.
def _pontas_do_mes(mes):
    """`'2026-02'` -> `('2026-02-01', '2026-02-28')`.

    Nome comprido de proposito: `_mes` neste arquivo ja e a funcao que corta
    `2026-01-05 00:00:00.000` em `2026-01`, e as duas juntas leem o mesmo tipo
    de texto em direcoes opostas."""
    ano, numero = (int(parte) for parte in mes.split("-"))
    return f"{mes}-01", f"{mes}-{calendar.monthrange(ano, numero)[1]:02d}"


# =============================================================== filtros
def test_filtros_recusam_o_que_o_contrato_nao_admite():
    matriz.Filtros(de="2026-01-01", ate="2026-03-31").validar()

    for kwargs, esperado in (
        ({"movimento": "xpto"}, "movimento"),
        ({"lente": "xpto"}, "lente"),
        ({"faixa": "xpto"}, "faixa"),
        ({"pagina": 0}, "pagina"),
    ):
        with pytest.raises(matriz.FiltroInvalido, match=esperado):
            matriz.Filtros(de="2026-01-01", ate="2026-03-31", **kwargs).validar()

    with pytest.raises(matriz.FiltroInvalido, match="AAAA-MM-DD"):
        matriz.Filtros(de="janeiro", ate="2026-03-31").validar()
    with pytest.raises(matriz.FiltroInvalido, match="invertido"):
        matriz.Filtros(de="2026-03-01", ate="2026-01-31").validar()

    # Mes fechado deixou de ser aceito: o recorte e por dia, e uma unica
    # linguagem de formato e o que impede a tela de pedir uma coisa e o
    # download de levar outra.
    with pytest.raises(matriz.FiltroInvalido, match="AAAA-MM-DD"):
        matriz.Filtros(de="2026-01", ate="2026-03").validar()
    # Formato que o `date.fromisoformat` aceitaria sozinho, e a tela nunca manda
    with pytest.raises(matriz.FiltroInvalido, match="AAAA-MM-DD"):
        matriz.Filtros(de="20260101", ate="2026-03-31").validar()
    # data que nao existe no calendario
    with pytest.raises(matriz.FiltroInvalido, match="nao e uma data"):
        matriz.Filtros(de="2026-02-30", ate="2026-03-31").validar()

    for dia in ("0", "32", "-1", "x", "1.5"):
        with pytest.raises(matriz.FiltroInvalido, match="dia"):
            matriz.Filtros(de="2026-01-01", ate="2026-03-31",
                           dias=(dia,)).validar()


def test_dia_do_mes_normaliza_para_o_eco_e_o_sql_falarem_do_mesmo_conjunto():
    """Repetido e fora de ordem viram um conjunto ordenado de inteiros.

    Nao e estetica: `como_dict()` e o que a auditoria grava, e o `WHERE` sai da
    mesma tupla. Se cada ponta normalizasse por conta propria, o registro de
    download poderia descrever um recorte diferente do que saiu."""
    filtros = matriz.Filtros(de="2026-01-01", ate="2026-01-31",
                             dias=("06", 6, "4", " 9 ")).validar()
    assert filtros.dias == (4, 6, 9)
    assert filtros.como_dict()["dias"] == [4, 6, 9]

    clausulas, params = recorte.onde(filtros)
    assert params["dias"] == [4, 6, 9]
    assert any("EXTRACT(DAY FROM f.nk_calendario)" in c for c in clausulas)

    # Sem filtro de dia, a clausula nao existe -- nao e `IN (1..31)`, que
    # cobraria o preco de uma expressao sem indice para nao filtrar nada.
    _, sem = recorte.onde(matriz.Filtros(de="2026-01-01", ate="2026-01-31").validar())
    assert "dias" not in sem


def test_ponta_de_mes_parcial_aparece_no_cabecalho():
    """`2026-08 (03-31)`: total rotulado como o mes que nao e o mes inteiro e o
    numero que alguem copia para um relatorio sem saber."""
    rotulos = recorte.rotulos_dos_meses("2026-08-03", "2026-09-05")
    assert rotulos == {"2026-08": "2026-08 (03-31)", "2026-09": "2026-09 (01-05)"}

    # mes inteiro sai sem parenteses: anotar o obvio treina a pessoa a ignorar
    # a anotacao
    assert recorte.rotulos_dos_meses("2026-01-01", "2026-02-28") == {
        "2026-01": "2026-01", "2026-02": "2026-02",
    }
    # um mes so, parcial nas duas pontas
    assert recorte.rotulos_dos_meses("2026-05-10", "2026-05-12") == {
        "2026-05": "2026-05 (10-12)",
    }
    # fevereiro de ano bissexto termina em 29, e o rotulo tem que saber disso
    assert recorte.rotulos_dos_meses("2028-02-01", "2028-02-29") == {
        "2028-02": "2028-02",
    }


def test_o_aviso_do_filtro_de_dia_resume_em_faixas():
    """Aviso que lista 28 numeros e uma parede que ninguem le -- e aviso que
    ninguem le nao avisa nada."""
    assert recorte.rotulo_dos_dias([4, 5, 6, 9, 20, 21]) == "04 a 06, 09, 20, 21"
    assert recorte.rotulo_dos_dias([31]) == "31"
    assert recorte.rotulo_dos_dias([]) == ""
    assert recorte.aviso_dos_dias(()) is None
    assert "04 a 06" in recorte.aviso_dos_dias([4, 5, 6])


def test_mes_vazio_vira_coluna_vazia_e_nao_coluna_ausente():
    """Se a coluna do mes sem dado desaparecesse, as outras deslizariam e a
    comparacao entre linhas passaria a mentir."""
    assert matriz.meses_do_periodo("2026-01-01", "2026-04-30") == [
        "2026-01", "2026-02", "2026-03", "2026-04"
    ]
    assert matriz.meses_do_periodo("2025-11-01", "2026-02-28") == [
        "2025-11", "2025-12", "2026-01", "2026-02"
    ]
    assert matriz.meses_do_periodo("2026-05-01", "2026-05-31") == ["2026-05"]
    # O mes da ponta entra INTEIRO como coluna mesmo quando o periodo pega
    # poucos dias dele: a coluna existe, e o cabecalho declara os dias.
    assert matriz.meses_do_periodo("2026-08-31", "2026-09-01") == [
        "2026-08", "2026-09"
    ]
    assert matriz.meses_do_periodo("2026-05-10", "2026-05-12") == ["2026-05"]


def test_hierarquia_e_configuravel():
    """O terceiro nivel foi lido do contrato escrito, nao do artefato (que nao
    existe mais). Este teste fixa que trocar de nivel e mudar `HIERARQUIA`, e
    que a saida tem o nivel `faixa` e a entrada nao."""
    assert matriz.HIERARQUIA["rec"] == ("unidade", "cliente", "operacao")
    assert matriz.HIERARQUIA["exp"] == ("unidade", "cliente", "faixa", "operacao")
    assert matriz.FAIXA not in matriz.HIERARQUIA["rec"], \
        "entrada nao tem faixa: a medida nao se repete nela"
    for niveis in matriz.HIERARQUIA.values():
        for nivel in niveis:
            assert nivel == matriz.FAIXA or nivel in matriz.NIVEL, \
                f"nivel {nivel!r} nao tem definicao de SQL em NIVEL"


def test_pallet_nao_existe_na_saida():
    """Contrato: pallet so existe na entrada. Nenhuma das 3 faixas da expedicao
    tem a medida -- e a fonte, nao defeito."""
    assert contrato.LENTES["pal"]["rec"] == "qtde_pallet"
    for faixa in contrato.FAIXAS:
        assert contrato.coluna_exp("pal", faixa) is None
    assert matriz._medidas_da_consulta("exp", "pal") == {}
    assert matriz._medidas_da_consulta("rec", "pal") == {"": "qtde_pallet"}
    # as outras quatro lentes existem nas tres faixas
    for lente in ("liq", "bru", "vol", "val"):
        assert len(matriz._medidas_da_consulta("exp", lente)) == 3


# ========================================================= banco real
@tem_extracao
def test_aceite_celula_por_celula_contra_os_csvs(banco_migrado):
    """**O aceite do V3.2.** Duas implementacoes independentes, mesmo numero.

    Carrega os dois CSVs, calcula a Matriz pelo SQL e em Python puro, e compara
    celula por celula -- entrada e saida, e mais de uma lente."""
    carregar_tudo(FonteCSV(DIRETORIO_DW))
    conn = psycopg2.connect(__import__("os").environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            for movimento, lente in (("rec", "liq"), ("rec", "pal"),
                                     ("exp", "liq"), ("exp", "val")):
                de, ate = "2026-01-01", "2026-08-31"
                # pagina grande o suficiente para nao cortar unidade: o aceite
                # e sobre o numero, e paginacao tem teste proprio
                resultado = matriz.matriz(cur, matriz.Filtros(
                    de=de, ate=ate, movimento=movimento, lente=lente,
                ))
                do_sql = _folhas(resultado["linhas"])
                do_csv = esperado_do_csv(movimento, lente, de, ate)

                rotulo = f"{movimento}/{lente}"
                assert do_sql, f"{rotulo}: a Matriz voltou vazia"
                assert set(do_sql) == set(do_csv), (
                    f"{rotulo}: conjunto de celulas divergiu -- "
                    f"so no SQL: {sorted(set(do_sql) - set(do_csv))[:3]}; "
                    f"so no CSV: {sorted(set(do_csv) - set(do_sql))[:3]}"
                )
                for chave, esperado in do_csv.items():
                    assert do_sql[chave] == esperado, \
                        f"{rotulo}: celula {chave} -- SQL {do_sql[chave]}, CSV {esperado}"

                # e o total geral fecha com a soma das folhas do CSV
                if movimento == "rec":
                    esperado_total = defaultdict(Decimal)
                    for chave_csv, valor in do_csv.items():
                        mes = chave_csv[-1]
                        esperado_total[mes] += valor
                    for mes, valor in esperado_total.items():
                        assert resultado["total"][mes] == valor, \
                            f"{rotulo}: total de {mes} divergiu"
    finally:
        conn.close()


@tem_extracao
def test_no_de_cima_e_a_soma_dos_filhos(banco_migrado):
    """A tela mostra o total da unidade sem somar os filhos no JavaScript --
    entao o backend tem que garantir a coerencia dos dois."""
    carregar_tudo(FonteCSV(DIRETORIO_DW))
    conn = psycopg2.connect(__import__("os").environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            resultado = matriz.matriz(cur, matriz.Filtros(
                de="2026-01-01", ate="2026-03-31", movimento="rec", lente="liq"))
            for unidade in resultado["linhas"]:
                for mes in resultado["meses"]:
                    soma = sum(
                        filho["valores"].get(mes) or 0
                        for filho in unidade["filhos"]
                    )
                    proprio = unidade["valores"].get(mes) or 0
                    assert proprio == soma, (
                        f"unidade {unidade['chave']} em {mes}: no diz {proprio}, "
                        f"filhos somam {soma}"
                    )
    finally:
        conn.close()


def test_saida_abre_as_tres_faixas_com_filhos_proprios(cursor):
    """A hierarquia da saida e `faixa -> tipo de saida`: expandir "Atendido pelo
    estoque" mostra as operacoes DAQUELA faixa, nao as da faixa do botao.

    E o no de cima mostra a faixa escolhida -- as tres nao somam entre si."""
    _semear_saida(cursor)
    resultado = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="exp", lente="liq",
        faixa="solicitado"))

    unidade = resultado["linhas"][0]
    cliente = unidade["filhos"][0]
    faixas = {no["chave"]: no for no in cliente["filhos"]}

    assert list(faixas) == list(contrato.FAIXAS), \
        "as tres faixas ficam na ordem do relatorio -- e leitura, nao ranking"
    assert faixas["solicitado"]["valores"]["2026-01"] == Decimal("100.000")
    assert faixas["atendido"]["valores"]["2026-01"] == Decimal("80.000")
    assert faixas["separado"]["valores"]["2026-01"] == Decimal("70.000")

    # cada faixa leva os seus proprios filhos, com o valor DELA
    for nome, esperado in (("solicitado", "100.000"), ("atendido", "80.000"),
                           ("separado", "70.000")):
        filhos = faixas[nome]["filhos"]
        assert [f["chave"] for f in filhos] == ["SAIDA NORMAL"], \
            f"faixa {nome} ficou sem filho proprio"
        assert filhos[0]["valores"]["2026-01"] == Decimal(esperado)

    # o no de cima mostra a faixa ESCOLHIDA, nao a soma das tres
    assert cliente["valores"]["2026-01"] == Decimal("100.000")
    assert unidade["valores"]["2026-01"] == Decimal("100.000")
    assert any("não somam entre si" in a for a in resultado["avisos"])

    # trocar a faixa do botao troca o que o nivel de cima mostra
    outra = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="exp", lente="liq",
        faixa="atendido"))
    assert outra["linhas"][0]["valores"]["2026-01"] == Decimal("80.000")


def test_pallet_na_saida_volta_vazio_com_aviso(cursor):
    """Escolher Pallets na saida mostra coluna vazia e declara por que. O aviso
    so aparece quando o caso ocorre -- disciplina do
    memory/pagina-mostra-numero-nao-texto.md."""
    _semear_saida(cursor)
    resultado = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="exp", lente="pal"))
    assert resultado["linhas"] == []
    assert resultado["total"] == {"2026-01": None}
    assert any("só existe na entrada" in a for a in resultado["avisos"])

    # na entrada a mesma lente tem numero, e nenhum aviso de pallet
    _semear_entrada(cursor)
    entrada = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="rec", lente="pal"))
    assert entrada["total"]["2026-01"] == 7
    assert not any("só existe na entrada" in a for a in entrada["avisos"])


def test_dimensao_faltando_nao_faz_a_linha_desaparecer(cursor):
    """Nao ha FK do fato para as dimensoes (V3.0). Unidade que ainda nao entrou
    em `cat_unidades` tem que aparecer com a sigla crua -- desaparecer em
    silencio deixaria o numero menor sem ninguem ver."""
    _semear_entrada(cursor, sigla="NOVA", cliente="99999999")
    cursor.execute("DELETE FROM cat_unidades")
    cursor.execute("DELETE FROM cat_clientes")

    resultado = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="rec", lente="liq"))
    unidade = resultado["linhas"][0]
    assert unidade["chave"] == "NOVA", "a unidade sem dimensao sumiu da Matriz"
    assert unidade["rotulo"] == "NOVA", "sem dimensao, o rotulo cai para a fonte"
    cliente = unidade["filhos"][0]
    assert cliente["chave"] == "99999999"
    assert cliente["rotulo"], "cliente sem dimensao ficou sem rotulo nenhum"


def test_filtros_recortam_de_verdade(cursor):
    """Filtro que nao filtra e pior que filtro ausente: a tela afirma um recorte
    que o numero nao respeita."""
    _semear_entrada(cursor, sigla="RMSPII", cliente="11111111", peso="10.000")
    _semear_entrada(cursor, sigla="CWBIII", cliente="22222222", peso="20.000",
                    gem="0000000002")

    def total(mes="2026-01", **kwargs):
        de, ate = _pontas_do_mes(mes)
        r = matriz.matriz(cursor, matriz.Filtros(
            de=de, ate=ate, movimento="rec", lente="liq", **kwargs))
        return r["total"][mes]

    assert total() == Decimal("30.000")
    assert total(unidades=("RMSPII",)) == Decimal("10.000")
    assert total(clientes=("22222222",)) == Decimal("20.000")
    assert total(operacoes=("SAIDA NORMAL",)) is None, \
        "operacao que nao existe no recorte deveria zerar"
    assert total(unidades=("RMSPII", "CWBIII")) == Decimal("30.000")
    # periodo fora do dado
    assert total(mes="2026-05") is None


def test_periodo_recorta_pelo_calendario_e_nao_pela_solicitacao(cursor):
    """Decisao A-5: a Matriz agrega por `nk_calendario`, a data do MOVIMENTO.
    Guia pedida em 31/jan e expedida em 02/fev conta em fevereiro."""
    _semear_entrada(cursor, calendario="2026-02-02", solic="2026-01-31",
                    peso="55.000")
    fevereiro = matriz.matriz(cursor, matriz.Filtros(
        de="2026-02-01", ate="2026-02-28", movimento="rec", lente="liq"))
    janeiro = matriz.matriz(cursor, matriz.Filtros(
        de="2026-01-01", ate="2026-01-31", movimento="rec", lente="liq"))
    assert fevereiro["total"]["2026-02"] == Decimal("55.000")
    assert janeiro["total"]["2026-01"] is None, \
        "agregou pela data da solicitacao -- contraria a decisao A-5"


@tem_extracao
def test_aceite_do_recorte_por_dia_contra_os_csvs(banco_migrado):
    """**O aceite do recorte por dia.** Duas implementacoes, mesmo numero.

    Mesmo metodo do aceite do V3.2, com o recorte que o lote criou: periodo
    comecando e terminando no MEIO do mes, e filtro de dia do mes por cima. Se o
    `WHERE` e o caminho em Python discordarem de uma celula, este teste diz qual.

    Por que isto e o teste que importa neste lote: um recorte que corta errado
    nao estoura -- ele devolve um numero menor, plausivel, e ninguem ve."""
    carregar_tudo(FonteCSV(DIRETORIO_DW))
    conn = psycopg2.connect(__import__("os").environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            for de, ate, dias in (
                ("2026-03-03", "2026-05-05", ()),        # pontas parciais
                ("2026-02-01", "2026-04-30", (1, 2, 3)), # dia do mes, meses inteiros
                ("2026-06-10", "2026-07-20", (10, 11, 12, 13, 14, 15)),  # os dois
            ):
                filtros = matriz.Filtros(de=de, ate=ate, movimento="rec",
                                         lente="liq", dias=dias)
                resultado = matriz.matriz(cur, filtros)
                do_sql = _folhas(resultado["linhas"])
                do_csv = esperado_do_csv("rec", "liq", de, ate,
                                         dias=recorte.dias_do_filtro(dias))

                rotulo = f"{de} a {ate} dias={dias or 'todos'}"
                assert do_sql, f"{rotulo}: a Matriz voltou vazia"
                assert set(do_sql) == set(do_csv), (
                    f"{rotulo}: conjunto de celulas divergiu -- "
                    f"so no SQL: {sorted(set(do_sql) - set(do_csv))[:3]}; "
                    f"so no CSV: {sorted(set(do_csv) - set(do_sql))[:3]}"
                )
                for chave, esperado in do_csv.items():
                    assert do_sql[chave] == esperado, f"{rotulo}: celula {chave}"

                # o cabecalho tem que declarar as pontas parciais
                rotulos = resultado["rotulos_meses"]
                primeiro, ultimo = resultado["meses"][0], resultado["meses"][-1]
                if not de.endswith("-01"):
                    assert "(" in rotulos[primeiro], (
                        f"{rotulo}: a coluna {primeiro} e parcial e o cabecalho "
                        "nao declara"
                    )
                if dias:
                    assert any("dia do mês" in a for a in resultado["avisos"]), (
                        f"{rotulo}: filtro de dia ativo sem aviso na tela"
                    )
    finally:
        conn.close()


@tem_extracao
def test_total_linhas_da_matriz_bate_com_a_contagem_da_planilha(banco_migrado):
    """O `total_linhas` que a Matriz devolve (soma dos `count(*)` dos grupos) e o
    numero que a tela usa para avisar antes de um download grande.

    Ele tem que ser o MESMO que a planilha conta com `count(*)` sobre o recorte
    inteiro. Se divergirem, a tela avisa sobre um arquivo e baixa outro."""
    from catering.consulta import planilha as mod_planilha

    carregar_tudo(FonteCSV(DIRETORIO_DW))
    conn = psycopg2.connect(__import__("os").environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            for de, ate, dias in (
                ("2026-01-01", "2026-08-31", ()),
                ("2026-03-03", "2026-05-05", ()),
                ("2026-01-01", "2026-08-31", (1, 15, 31)),
            ):
                filtros = matriz.Filtros(de=de, ate=ate, dias=dias)
                da_matriz = matriz.matriz(cur, filtros)["total_linhas"]
                da_planilha = mod_planilha.planilha(
                    cur, matriz.Filtros(de=de, ate=ate, dias=dias)
                )["paginacao"]["total_linhas"]
                assert da_matriz == da_planilha, (
                    f"{de} a {ate} dias={dias or 'todos'}: a Matriz contou "
                    f"{da_matriz} linha(s) e a planilha {da_planilha}"
                )
                assert da_matriz > 0, "recorte com dado voltou contagem zero"
    finally:
        conn.close()


# ------------------------------------------------------------- semeadura
_COMUNS = (
    "pk_dw, dw_processo, dw_data_inclusao, dw_data_alteracao, sk_calendario,"
    " sk_instancia, sk_empresa, sk_filial, sk_cliente, nk_calendario,"
    " nk_instancia, nk_empresa, nk_filial, nk_wms_filial, nk_qls_filial,"
    " nk_slin_empresa, nk_slin_filial, nk_cliente, nk_wms_cliente, data_solic,"
    " ano_solic, nome_und, num_gem, cnpj_cpf_cli, raz_social, descr_oper_wms,"
    " nome_estoque, status_processo, flg_interface"
)


def _carga(cur, tabela):
    cur.execute(
        "INSERT INTO cat_cargas (tabela_origem, fonte, status) "
        "VALUES (%s, 'csv', 'ok') RETURNING id", (tabela,))
    return cur.fetchone()[0]


def _valores(sigla, cliente, gem, operacao, calendario, solic):
    return (
        1, contrato.PROCESSO_DW, "2026-08-20 15:00:00", "2026-08-20 15:00:00",
        1, 1, 1, 1, 1, calendario, "SLIN_RMSPII_PRD", "SF", "06975242000187",
        sigla, sigla, "001", "001", cliente, "X", solic, 2026,
        f"{sigla} - TESTE", gem, f"{cliente}0001", "CLIENTE TESTE", operacao,
        "CONGELADO", "Concluido", "D",
    )


def _semear_entrada(cur, sigla="RMSPII", cliente="67945071", gem="0000000001",
                    operacao="NAO TROCA NOTA DE ARMAZENAGEM", peso="100.000",
                    calendario="2026-01-05", solic="2026-01-05"):
    carga = _carga(cur, contrato.TABELA_REC)
    cur.execute(
        f"INSERT INTO cat_fato_recebimento (carga_id, {_COMUNS},"
        " qtde_sku, qtde_pallet, qtde_vol2, qtde_peso2, qtde_pbrt2, qtde_vlr)"
        " VALUES (%s" + ", %s" * 29 + ", 1, 7, 10, %s, %s, %s)",
        (carga,) + _valores(sigla, cliente, gem, operacao, calendario, solic)
        + (peso, peso, peso),
    )


def _semear_saida(cur, sigla="RMSPII", cliente="67945071", gem="0000000001",
                  operacao="SAIDA NORMAL", calendario="2026-01-05"):
    """Solicitado 100, atendido 80, separado 70 -- as tres faixas com valores
    distintos, para dar para provar qual delas a tela mostrou."""
    carga = _carga(cur, contrato.TABELA_EXP)
    cur.execute(
        f"INSERT INTO cat_fato_expedicao (carga_id, {_COMUNS},"
        " qtde_pedido,"
        " qtde_sku_solicitado, qtde_vol_solicitado, qtde_peso_solicitado,"
        " qtde_pbrt_solicitado, qtde_vlr_solicitado,"
        " qtde_sku_atendido, qtde_vol_atendido, qtde_peso_atendido,"
        " qtde_pbrt_atendido, qtde_vlr_atendido,"
        " qtde_sku_separado, qtde_vol_separado, qtde_peso_separado,"
        " qtde_pbrt_separado, qtde_vlr_separado)"
        " VALUES (%s" + ", %s" * 29 + ", 1,"
        " 1, 10, 100.000, 100.000, 100.000,"
        " 1, 8, 80.000, 80.000, 80.000,"
        " 1, 7, 70.000, 70.000, 70.000)",
        (carga,) + _valores(sigla, cliente, gem, operacao, calendario, calendario),
    )
