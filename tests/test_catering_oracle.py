"""V3.5 -- a FonteOracle: SQL gerado, contrato, coercao nativa e somente leitura.

## O limite desta suite, dito antes de qualquer coisa

**Nenhum teste daqui conecta no DW.** O DW e producao, e a politica do projeto
e que a IA nao conecta nele. Tudo aqui roda contra `ConexaoFalsa`, um driver de
mentira com a mesma superficie estreita que a `FonteOracle` usa.

O que isso prova de verdade: o **statement** que sai, os **binds**, a
conferencia de contrato, a coercao de valor nativo, e que nenhum caminho do
modulo emite comando de escrita.

O que isso **nao** prova: que o Oracle honra o `>` do `WHERE`, que os nomes
reais das colunas sao os do contrato, e que o volume e o esperado. Essas tres
so a rodada da Maria prova -- e e por isso que existe
`python -m catering.carga --fonte oracle --sondar`, cuja saida e o aceite do
lote (ver `docs/V3_PLANO.md`, secao do V3.5).

## Duas guardas de somente leitura, e nao uma

Mesmo par do cliente do Graph (`tests/test_graph_datahub.py`), pelo mesmo
motivo:

  - **estatica**, sobre a arvore sintatica: nenhum literal do modulo contem
    palavra de escrita, e nenhuma chamada a `commit`/`rollback`/`executemany`.
    Ela pega o codigo que ninguem exercitou;
  - **de runtime**, no `ConexaoFalsa`: todo `execute` que nao comece por
    `SELECT` estoura. Ela pega o comando montado por concatenacao, que a
    estatica nao veria.

## Valor nativo, que e o ponto do lote

`linha_nativa()` monta a linha como o **driver** a entrega: `Decimal`,
`datetime` e `str` -- nao o texto que o CSV entrega. O mesmo
`transformacao.transformar()` recebe as duas e tem que produzir o mesmo
resultado. Sem isso, "adaptador" seria intencao e nao fato.
"""

import ast
import pathlib
import re
from datetime import date, datetime
from decimal import Decimal

import pytest

from catering import contrato
from catering.carga import carregar_movimento, destino, fonte_oracle
from catering.carga import transformacao as tr
from tests.conftest import consultar

# ------------------------------------------------------------ linha nativa
# Como o `oracledb` entrega cada tipo do contrato, com `fetch_decimals` ligado:
# NUMBER vira `Decimal` (inclusive nas colunas de contagem), DATE e TIMESTAMP
# viram `datetime`, VARCHAR2 vira `str`.
_NATIVO_POR_TIPO = {
    "TEXT": "X",
    "INTEGER": Decimal("1"),
    "SMALLINT": Decimal("2026"),
    "NUMERIC(18,3)": Decimal("25290.217"),
    "DATE": datetime(2026, 1, 5, 0, 0, 0),
    "TIMESTAMP": datetime(2026, 8, 20, 15, 26, 39),
}

# Valores que precisam ser plausiveis e nao so do tipo certo: a instancia tem
# que ser SLIN (escopo) e os identificadores tem zero a esquerda.
_PADRAO = {
    "dw_processo": contrato.PROCESSO_DW,
    "nk_instancia": "SLIN_RMSPII_PRD",
    "nk_empresa": "SF",
    "nk_filial": "06975242000187",
    "nk_wms_filial": "RMSPII",
    "nk_qls_filial": "RMSPII",
    "nk_slin_empresa": "001",
    "nk_slin_filial": "001",
    "nk_cliente": "67945071",
    "nk_wms_cliente": "SAPORE S.A",
    "nome_und": "RMSPII - BARUERI",
    "num_gem": "0000000035",
    "cnpj_cpf_cli": "67945071000138",
    "raz_social": "SAPORE S.A",
    "descr_oper_wms": "SAIDA NORMAL",
    "nome_estoque": "CONGELADO",
    "status_processo": "Concluido",
    "flg_interface": "D",
}


def linha_nativa(movimento, **sobrescritas):
    """Uma linha como o driver a devolve: **tupla**, na ordem do contrato.

    Tupla e nao dict de proposito -- e o que o `cursor` entrega, e casar tupla
    com nome de coluna e justamente o trabalho que a `FonteOracle` faz."""
    valores = []
    for nome, tipo, _nulo in contrato.colunas(movimento):
        if nome in sobrescritas:
            valores.append(sobrescritas[nome])
        else:
            valores.append(_PADRAO.get(nome, _NATIVO_POR_TIPO[tipo]))
    return tuple(valores)


# ------------------------------------------------------------ driver falso
class CursorFalso:
    """Só o que a `FonteOracle` usa: execute, description, fetchone, iteracao.

    Cursor de mentira estreito e de proposito: se a `FonteOracle` passar a
    depender de mais coisa do driver, isto quebra e o teste vira a conversa
    sobre a dependencia nova."""

    def __init__(self, conexao):
        self.conexao = conexao
        self.description = None
        self.arraysize = 100
        self.prefetchrows = 2
        self._resultado = iter(())

    def __enter__(self):
        return self

    def __exit__(self, *_excecao):
        return False

    def execute(self, sql, binds=None):
        self.conexao.executados.append((sql, dict(binds or {})))
        # Guarda de RUNTIME: nada que nao seja leitura passa por aqui.
        if not sql.lstrip().upper().startswith("SELECT"):
            raise AssertionError(f"comando que nao e leitura: {sql!r}")
        if self.conexao.erro is not None:
            raise self.conexao.erro

        if sql.rstrip().endswith("WHERE 1=0"):
            self.description = self.conexao.description
            self._resultado = iter(())
        elif "COUNT(DISTINCT" in sql.upper():
            self._resultado = iter([self.conexao.identidade])
        elif "HAVING COUNT(*) > 1" in sql.upper():
            self._resultado = iter(self.conexao.colisoes)
        elif "GROUP BY ANO_SOLIC" in sql.upper():
            self._resultado = iter(self.conexao.discordantes)
        elif sql.lstrip().upper().startswith("SELECT COUNT(*)"):
            self._resultado = iter([self.conexao.resumo])
        else:
            self.description = self.conexao.description
            self._resultado = iter(self.conexao.linhas)

    def fetchone(self):
        return next(self._resultado, None)

    def __iter__(self):
        return self._resultado


class ConexaoFalsa:
    """Conexao de mentira. Guarda o que foi executado e se foi fechada."""

    def __init__(self, movimento="rec", linhas=(), resumo=None, erro=None,
                 colunas=None, identidade=None, colisoes=(), discordantes=()):
        self.description = [
            (nome,) for nome in (colunas or fonte_oracle.colunas_dw(movimento))
        ]
        self.linhas = list(linhas)
        self.resumo = resumo
        # (total, um distinto por candidato de CANDIDATOS_DE_IDENTIDADE, e por
        # ultimo as linhas em que ano_solic discorda do ano de data_solic)
        self.identidade = identidade or (
            (1,) * (1 + len(fonte_oracle.CANDIDATOS_DE_IDENTIDADE)) + (0,)
        )
        self.colisoes = list(colisoes)
        self.discordantes = list(discordantes)
        self.erro = erro
        self.executados = []
        self.fechada = False

    def cursor(self):
        return CursorFalso(self)

    def close(self):
        self.fechada = True


def _resumo_falso(na_tabela, na_janela):
    """O que `sql_resumo` devolve: 8 posicoes -- contagem e datas da tabela
    inteira, e as mesmas coisas dentro da janela.

    Duas contagens porque o `--sondar` mostra as duas, e ver a diferenca e o que
    impede alguem de concluir que o DW esta faltando dado quando o recorte e
    nosso."""
    return (
        Decimal(str(na_tabela)),
        datetime(2023, 1, 2), datetime(2026, 8, 25),            # na tabela
        Decimal(str(na_janela)),
        datetime(2026, 1, 2), datetime(2026, 8, 25),            # na janela
        datetime(2026, 8, 25, 10, 31), datetime(2026, 8, 25, 13, 48),
    )


def fonte_com(conexao):
    """`FonteOracle` apontada para uma conexao falsa. A injecao existe so para
    o teste: em producao o padrao e a conexao real."""
    return fonte_oracle.FonteOracle(abrir_conexao=lambda: conexao)


# ================================================================ o SQL
def test_select_e_gerado_do_contrato_e_nunca_estrela():
    """A lista explicita e o que faz coluna removida no DW dar `ORA-00904`
    nomeando a coluna, no primeiro execute -- e nao erro de tipo trinta mil
    linhas adiante."""
    for movimento in contrato.MOVIMENTOS:
        sql, binds = fonte_oracle.sql_select(movimento)
        esperadas = [
            contrato.coluna_dw(nome, movimento)
            for nome, _tipo, _nulo in contrato.colunas(movimento)
        ]
        prefixo = "SELECT " + ", ".join(esperadas) + " FROM "
        assert sql.startswith(prefixo), (
            f"{movimento}: o SELECT precisa levar as colunas do contrato na "
            f"ordem do schema. Veio: {sql[:200]}"
        )
        assert "SELECT *" not in sql, f"{movimento}: leitura de dado com estrela"
        assert f" FROM {contrato.tabela(movimento)}" in sql, (
            f"{movimento}: a tabela precisa ser a qualificada de "
            "contrato.tabela()"
        )
        assert binds == {"piso": contrato.piso_do_periodo()}, (
            "o piso de periodo vale em toda rodada, com ou sem `desde`"
        )


def test_desde_entra_como_bind_e_nunca_concatenado():
    """Timestamp interpolado numa string de SQL e o defeito que nao aparece na
    revisao e que ninguem consegue explicar depois."""
    desde = datetime(2026, 8, 24, 17, 46, 39)
    sql, binds = fonte_oracle.sql_select("rec", desde)

    assert sql.endswith("AND DW_DATA_ALTERACAO > :desde"), sql[-80:]
    assert binds == {"piso": contrato.piso_do_periodo(), "desde": desde}
    assert "2026" not in sql, \
        "o valor do `desde` nao pode aparecer no SQL -- ele vai por bind"
    # Maior, e nao maior-ou-igual: `>=` releria a ultima linha da rodada
    # anterior a cada rodada, inflando `linhas_lidas` sem mudar nada.
    _antes, _, marca = sql.partition("AND ")
    assert marca == "DW_DATA_ALTERACAO > :desde", (
        "a marca d'agua compara com `>` e nao `>=`: igual e a linha que a "
        f"rodada anterior ja carregou. Veio: {marca}"
    )


def test_sem_desde_o_unico_filtro_e_o_piso_de_periodo():
    """A premissa "tabelas inteiras, sem filtro" do contrato valeu ate
    25/ago/2026, quando o DW passou a publicar 2023-2026 e a Maria recortou o
    escopo em 2026. Carga completa hoje significa "a janela inteira", e o
    `desde` continua sendo a unica coisa que o incremental acrescenta."""
    sql, binds = fonte_oracle.sql_select("exp")
    _antes, _, onde = sql.partition(" WHERE ")
    assert onde == "NK_CALENDARIO >= :piso"
    assert set(binds) == {"piso"}


def test_escopo_nao_e_filtrado_no_sql():
    """Empurrar `LIKE 'SLIN_%'` para o banco calaria o tripwire do V3.1, que
    conta e loga linha fora de escopo. O filtro fica em Python."""
    for movimento in contrato.MOVIMENTOS:
        sql, _ = fonte_oracle.sql_select(movimento, datetime(2026, 8, 1))
        _antes, _, onde = sql.partition(" WHERE ")
        # a clausula inteira, e nao "nao contem SLIN": `NK_SLIN_EMPRESA` e uma
        # coluna legitima da lista do SELECT, e procurar substring ali daria
        # falso positivo eterno
        assert onde == "NK_CALENDARIO >= :piso AND DW_DATA_ALTERACAO > :desde", (
            f"{movimento}: o WHERE tem que ser o piso e a marca d'agua, e "
            f"nada mais. Veio: {onde}"
        )
        assert "LIKE" not in sql.upper()
        assert f"'{contrato.PREFIXO_INSTANCIA}" not in sql,             "instancia como literal no SQL significa escopo filtrado no banco"


def test_movimento_desconhecido_nao_gera_sql():
    with pytest.raises(KeyError):
        fonte_oracle.sql_select("estoque")
    with pytest.raises(KeyError):
        next(fonte_com(ConexaoFalsa()).extrair("transporte"))


# ================================================= nome do objeto (A-7)
def test_nome_da_tabela_vem_de_configuracao(monkeypatch):
    """A-7: fica so a `_V01`, mas "nao programada" e ausencia de plano e nao
    garantia -- a `FATO_VOLUMETRIA` do mesmo schema ja esta em `_V04`. Trocar
    de versao tem que ser uma variavel de ambiente, nao um commit."""
    assert contrato.tabela("rec") == "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01"
    assert contrato.tabela("exp") == "DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01"

    monkeypatch.setenv("DW_TABELA_REC", "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V02")
    assert contrato.tabela("rec") == "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V02"
    sql, _ = fonte_oracle.sql_select("rec")
    assert " FROM DM_VOLUMETRIA.FATO_VOL_REC_CAT_V02" in sql
    # o outro movimento nao e afetado pela variavel do primeiro
    assert contrato.tabela("exp") == "DM_VOLUMETRIA.FATO_VOL_EXP_CAT_V01"


def test_nome_de_objeto_invalido_nao_chega_no_sql(monkeypatch):
    """Nome de objeto nao pode ser bind: ele e concatenado. Entao ele precisa de
    guarda propria, senao um valor de ambiente errado (ou hostil) vira SQL."""
    for ruim in ("x; DROP TABLE cat_fato_recebimento", "minuscula", "A B",
                 "DM_VOLUMETRIA.FATO' OR '1'='1"):
        monkeypatch.setenv("DW_TABELA_REC", ruim)
        with pytest.raises(contrato.TabelaInvalida, match="DW_TABELA_REC"):
            fonte_oracle.sql_select("rec")


def test_coluna_da_pk_nao_deriva_do_nome_da_tabela():
    """A armadilha que este lote desarmou: `RENOMEADAS` montava o nome da
    coluna como `"PK_" + TABELA_REC`. Com a tabela qualificada isso produziria
    `PK_DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01`, que nao existe. A tabela ganhou
    schema e sufixo de versao; a coluna, nao."""
    assert contrato.coluna_dw("pk_dw", "rec") == "PK_FATO_VOL_REC_CAT"
    assert contrato.coluna_dw("pk_dw", "exp") == "PK_FATO_VOL_EXP_CAT"
    for movimento in contrato.MOVIMENTOS:
        sql, _ = fonte_oracle.sql_select(movimento)
        assert "PK_DM_VOLUMETRIA" not in sql


# ================================================== contrato de colunas
def test_contrato_e_conferido_antes_de_qualquer_linha():
    """Mesma disciplina da `FonteCSV`, que confere o cabecalho antes da
    primeira linha. E o que faz coluna NOVA no DW aparecer -- a lista explicita
    do SELECT, sozinha, passaria por cima dela em silencio."""
    conexao = ConexaoFalsa("rec", linhas=[linha_nativa("rec")])
    list(fonte_com(conexao).extrair("rec"))

    primeiro = conexao.executados[0][0]
    assert primeiro.endswith("WHERE 1=0"), \
        f"a primeira consulta tem que ser a de zero linha; foi: {primeiro}"
    assert "SELECT *" in primeiro, \
        "a conferencia precisa de estrela: e ela que enxerga coluna nova"


def test_coluna_faltando_ou_sobrando_reprova_nomeando_a_coluna():
    """Nos dois sentidos: a que falta quebraria a carga adiante com erro
    obscuro, e a que sobra e coluna que o carregador nao grava -- descobrir isso
    pelo silencio custaria uma investigacao inteira."""
    completo = fonte_oracle.colunas_dw("rec")

    sem_uma = ConexaoFalsa("rec", colunas=[c for c in completo if c != "QTDE_PESO2"])
    with pytest.raises(tr.ContratoDivergente, match="QTDE_PESO2"):
        list(fonte_com(sem_uma).extrair("rec"))

    com_extra = ConexaoFalsa("rec", colunas=completo + ["QTDE_PESO_LIQUIDO_V2"])
    with pytest.raises(tr.ContratoDivergente, match="QTDE_PESO_LIQUIDO_V2"):
        list(fonte_com(com_extra).extrair("rec"))


def test_nomes_do_cursor_aceita_fetchinfo_e_tupla():
    """O `oracledb` devolve `FetchInfo` (que tambem se comporta como tupla).
    Aceitar as duas formas mantem o modulo indiferente a versao do driver."""
    class FetchInfoFalso:
        def __init__(self, nome):
            self.name = nome

    assert fonte_oracle.nomes_do_cursor([FetchInfoFalso("num_gem")]) == ["NUM_GEM"]
    assert fonte_oracle.nomes_do_cursor([("num_gem", "VARCHAR2")]) == ["NUM_GEM"]
    assert fonte_oracle.nomes_do_cursor(None) == []


# ======================================================= linha e coercao
def test_linha_crua_sai_com_as_chaves_do_dw():
    """A `FonteOracle` casa tupla com nome de coluna e devolve a linha CRUA,
    igual a `FonteCSV` -- coercao e trabalho da `transformacao.py`, nao de cada
    adaptador."""
    conexao = ConexaoFalsa("rec", linhas=[linha_nativa("rec", num_gem="0000000609")])
    linhas = list(fonte_com(conexao).extrair("rec"))

    assert len(linhas) == 1
    crua = linhas[0]
    assert crua["NUM_GEM"] == "0000000609"
    assert set(crua) == set(fonte_oracle.colunas_dw("rec")), \
        "as chaves da linha crua sao os nomes do DW, os mesmos que o CSV traz"


def test_valor_nativo_passa_pelo_mesmo_funil_do_texto():
    """O teste que sustenta o lote. O CSV entrega `'25290.217'`; o driver
    entrega `Decimal('25290.217')`. Os dois tem que produzir o MESMO resultado
    -- e o peso nao pode virar float no caminho, porque 3 decimais em binario de
    ponto flutuante perdem precisao contra `NUMERIC(18,3)`."""
    conexao = ConexaoFalsa("rec", linhas=[linha_nativa(
        "rec",
        qtde_peso2=Decimal("25290.217"),
        nk_calendario=datetime(2026, 1, 5, 0, 0, 0),
        dw_data_alteracao=datetime(2026, 8, 24, 17, 46, 39),
        pk_dw=Decimal("36592"),
    )])
    crua = next(iter(fonte_com(conexao).extrair("rec")))
    tipada = tr.transformar(crua, "rec")

    assert tipada["qtde_peso2"] == Decimal("25290.217")
    assert isinstance(tipada["qtde_peso2"], Decimal), \
        "peso em kg com 3 decimais nao pode passar por float"
    assert tipada["nk_calendario"] == date(2026, 1, 5)
    assert tipada["dw_data_alteracao"] == datetime(2026, 8, 24, 17, 46, 39)
    assert tipada["pk_dw"] == 36592
    assert tipada["num_gem"] == "0000000035", "zero a esquerda e texto, sempre"

    # o mesmo funil, agora com o texto que o CSV entrega para as MESMAS colunas
    assert tr.numero("25290.217") == tipada["qtde_peso2"]
    assert tr.dia("2026-01-05 00:00:00.000") == tipada["nk_calendario"]
    assert tr.instante("2026-08-24 17:46:39.000") == tipada["dw_data_alteracao"]
    assert tr.inteiro("36592") == tipada["pk_dw"]


def test_medida_vazia_do_driver_continua_virando_nulo():
    """A guia cancelada chega do Oracle com `None`, nao com string vazia.
    `NULL` mantem "cancelada" distinguivel de "pesou zero"."""
    conexao = ConexaoFalsa("rec", linhas=[linha_nativa(
        "rec", qtde_peso2=None, qtde_pbrt2=None, qtde_vol2=None, qtde_vlr=None,
    )])
    tipada = tr.transformar(next(iter(fonte_com(conexao).extrair("rec"))), "rec")
    for coluna in ("qtde_peso2", "qtde_pbrt2", "qtde_vol2", "qtde_vlr"):
        assert tipada[coluna] is None


def test_float_do_driver_com_decimal_fracionario_e_erro_em_coluna_inteira():
    """Se `fetch_decimals` estivesse desligado, `NUMBER` viria float. A coercao
    aceita float, mas uma contagem fracionaria e sinal de que algo esta errado
    na fonte -- e vira erro, nunca arredondamento."""
    with pytest.raises(tr.LinhaInvalida, match="fracionario"):
        tr.inteiro(1.5)
    assert tr.inteiro(3.0) == 3


# ==================================================== conexao e driver
def test_construir_a_fonte_nao_abre_conexao():
    """`--help` e erro de argumento nao podem tocar em producao."""
    chamadas = []

    def _nao_deveria():
        chamadas.append(1)
        raise AssertionError("a fonte conectou no construtor")

    fonte = fonte_oracle.FonteOracle(abrir_conexao=_nao_deveria)
    assert fonte.nome == "oracle"
    assert fonte.descrever("rec").startswith("DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01")
    assert chamadas == []


def test_a_conexao_e_fechada_mesmo_quando_a_leitura_quebra():
    """Conexao com producao pendurada e o tipo de vazamento que so aparece
    quando o DW comeca a recusar sessao nova."""
    conexao = ConexaoFalsa("rec", linhas=[linha_nativa("rec")])
    list(fonte_com(conexao).extrair("rec"))
    assert conexao.fechada, "carga que terminou bem tem que fechar a conexao"

    quebrada = ConexaoFalsa("rec", erro=RuntimeError("ORA-00942: table or view does not exist"))
    with pytest.raises(RuntimeError, match="ORA-00942"):
        list(fonte_com(quebrada).extrair("rec"))
    assert quebrada.fechada, "conexao tem que fechar tambem quando o DW recusa"


def test_descrever_nao_expoe_credencial():
    """`descrever()` vai para o log da carga agendada, que fica num arquivo na
    VM. Metade de uma credencial ja e informacao demais para um arquivo de
    log."""
    linha = fonte_oracle.FonteOracle().descrever("exp")
    assert "oracleprd-aws.superfrio.com.br:1521/pdwgener" in linha
    for proibido in ("DW_USER", "DW_SENHA", "password", "senha"):
        assert proibido not in linha


def test_dsn_vem_do_ambiente_com_padrao_medido(monkeypatch):
    """Host, porta e servico tem padrao porque nao sao segredo e ja estao no
    `DEPLOY.md`. Usuario e senha nao tem padrao -- e por isso o modulo, sozinho,
    nao conecta em lugar nenhum."""
    assert fonte_oracle.dsn() == "oracleprd-aws.superfrio.com.br:1521/pdwgener"
    monkeypatch.setenv("DW_HOST", "outro-host")
    monkeypatch.setenv("DW_BANCO", "outro_servico")
    assert fonte_oracle.dsn() == "outro-host:1521/outro_servico"


def test_credencial_ausente_falha_dizendo_o_nome_da_variavel(monkeypatch):
    monkeypatch.delenv("DW_USER", raising=False)
    monkeypatch.delenv("DW_SENHA", raising=False)
    with pytest.raises(fonte_oracle.CredencialAusente, match="DW_USER e DW_SENHA"):
        fonte_oracle.conectar()

    monkeypatch.setenv("DW_USER", "usuario-de-teste")
    with pytest.raises(fonte_oracle.CredencialAusente, match="DW_SENHA"):
        fonte_oracle.conectar()


def test_fetch_decimals_e_ligado_antes_de_conectar():
    """A linha que, faltando, corrompe peso em silencio: sem ela o `oracledb
    4.0.2` entrega `NUMBER` como float, e 3 decimais em binario de ponto
    flutuante nao voltam a ser o que eram."""
    oracledb = pytest.importorskip(
        "oracledb", reason="driver e dependencia de runtime; a suite do SQL nao precisa dele"
    )
    original = oracledb.defaults.fetch_decimals
    try:
        oracledb.defaults.fetch_decimals = False
        devolvido = fonte_oracle.configurar_driver()
        assert oracledb.defaults.fetch_decimals is True
        assert devolvido is oracledb
    finally:
        oracledb.defaults.fetch_decimals = original


def test_leitura_pede_lote_grande_antes_do_execute():
    """Com o default do driver (100 linhas), 42 mil linhas custam 420 idas e
    voltas na rede. `arraysize`/`prefetchrows` so valem se forem ajustados
    ANTES do execute -- por isso isto e teste e nao comentario."""
    class CursorVigiado(CursorFalso):
        def execute(self, sql, binds=None):
            if not sql.rstrip().endswith("WHERE 1=0"):
                assert self.arraysize == fonte_oracle.LOTE_LEITURA, \
                    "arraysize tem que estar ajustado antes do execute do dado"
                assert self.prefetchrows == fonte_oracle.LOTE_LEITURA + 1
            super().execute(sql, binds)

    conexao = ConexaoFalsa("exp", linhas=[linha_nativa("exp")])
    conexao.cursor = lambda: CursorVigiado(conexao)
    assert len(list(fonte_com(conexao).extrair("exp"))) == 1


# ========================================================= a sondagem
def test_sondar_devolve_a_evidencia_do_aceite():
    """O `--sondar` e o comando do aceite: ele tem que responder contrato,
    volume, as duas marcas d'agua e o tipo que chega -- sem escrever nada."""
    conexao = ConexaoFalsa(
        "rec",
        linhas=[linha_nativa("rec", qtde_peso2=Decimal("25290.217"))],
        resumo=_resumo_falso(36592, 36592),
    )
    resumo = fonte_com(conexao).sondar("rec")

    assert resumo["tabela"] == "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01"
    assert resumo["linhas"] == Decimal("36592"), "o que a tabela tem"
    assert resumo["linhas_na_janela"] == Decimal("36592"), "o que a carga grava"
    assert resumo["piso"] == contrato.piso_do_periodo()
    assert resumo["colunas_no_contrato"] == len(contrato.colunas("rec"))
    assert resumo["nk_calendario"] == (datetime(2023, 1, 2), datetime(2026, 8, 25)), (
        "o intervalo da TABELA -- e o que mostra que existe 2023 la, fora da "
        "nossa janela"
    )
    assert resumo["nk_calendario_na_janela"] == (
        datetime(2026, 1, 2), datetime(2026, 8, 25),
    ), "e o intervalo do que a carga grava"
    assert resumo["dw_data_alteracao"][1] == datetime(2026, 8, 25, 13, 48)

    # a amostra mostra o tipo que o driver entregou E o valor que o banco
    # recebe: e onde `fetch_decimals` aparece ou nao aparece
    tipo, bruto, tipado = resumo["amostra"]["qtde_peso2"]
    assert (tipo, bruto, tipado) == ("Decimal", "Decimal('25290.217')",
                                     "Decimal('25290.217')")
    assert resumo["amostra"]["num_gem"][2] == "'0000000035'"
    assert set(resumo["amostra"]) == set(fonte_oracle.AMOSTRA["rec"])


def test_sondar_nao_expoe_cliente_nem_cnpj():
    """A saida do sondar vai ser colada num documento. Nenhuma das colunas da
    amostra pode ser nome de cliente ou CNPJ."""
    proibidas = {"raz_social", "nk_wms_cliente", "cnpj_cpf_cli", "nk_cliente"}
    for movimento in contrato.MOVIMENTOS:
        assert not (set(fonte_oracle.AMOSTRA[movimento]) & proibidas)


def test_sondar_mede_se_a_chave_natural_ainda_e_unica():
    """O que a carga de 25/ago/2026 descobriu: a chave natural foi medida unica
    em 36.300 linhas **de 2026**, e o DW passou a publicar 2023-2026. Sem data
    na identidade, `num_gem` reciclado entre anos colide -- e o upsert recusa
    com "cannot affect row a second time".

    Esta medicao existe para a decisao ser tomada com numero, e nao com chute:
    ela diz se a chave de hoje repete, e se somar uma das duas datas resolve."""
    # total, e um distinto por candidato: chave de hoje repete; do ano_solic em
    # diante fica unica. Zero linha com ano_solic discordando de data_solic.
    conexao = ConexaoFalsa(
        "rec",
        linhas=[linha_nativa("rec")],
        resumo=_resumo_falso(201848, 36592),
        identidade=(Decimal("201848"), Decimal("174014"), Decimal("201848"),
                    Decimal("201848"), Decimal("201836"), Decimal("201848"),
                    Decimal("201848"), Decimal("0")),
        colisoes=[("0000000020", "RMSPII", Decimal("4"),
                   datetime(2023, 1, 3), datetime(2026, 1, 5))],
    )
    resumo = fonte_com(conexao).sondar("rec")

    ident = resumo["identidade"]
    assert ident["total"] == Decimal("201848")
    rotulos = [rotulo for rotulo, _valor in ident["candidatos"]]
    assert rotulos[0] == "chave de hoje" and rotulos[1] == "+ ano de data_solic", (
        "a ordem e a decisao: do mais grosso para o mais fino, e a chave certa "
        f"e a primeira unica. Veio {rotulos}"
    )
    por_rotulo = dict(ident["candidatos"])
    assert por_rotulo["chave de hoje"] < ident["total"], "e o caso que quebrou a carga"
    assert por_rotulo["+ ano de data_solic"] == ident["total"],         "o ano da solicitacao bastaria neste cenario"
    assert por_rotulo["+ ano de nk_calendario"] < ident["total"], (
        "e o numero que prova QUAL ano e o espaco de numeracao: o do pedido, "
        "nao o do movimento -- guia pedida em dezembro e movimentada em janeiro "
        "pertence a sequencia do ano anterior"
    )
    assert ident["ano_solic_discorda_de_data_solic"] == Decimal("0")

    # e a colisao vem com o intervalo de datas, que e o que separa as duas
    # explicacoes: gem reciclado entre anos, ou linha repetida no mesmo dia
    gem, filial, quantas, de, ate = resumo["colisoes"][0]
    assert (gem, filial, quantas) == ("0000000020", "RMSPII", Decimal("4"))
    assert de.year != ate.year, (
        "anos diferentes e o que diz que o num_gem se recicla; mesmo dia diria "
        "que o DW passou a publicar linha repetida, que pede resposta oposta"
    )


def test_sondar_detalha_o_ano_discordante_so_quando_ele_existe():
    """15 e 16 linhas discordando nao decidem nada; o FORMATO delas decide. Se
    for virada de ano (`ano_solic` 2025 com `data_solic` em janeiro/2026), e
    borda conhecida; se forem anos sem relacao, a coluna nao significa o que o
    nome diz e sai da disputa por identidade."""
    conexao = ConexaoFalsa(
        "rec",
        linhas=[linha_nativa("rec")],
        resumo=_resumo_falso(201848, 36592),
        identidade=(Decimal("201848"),) * 7 + (Decimal("15"),),
        discordantes=[(Decimal("2025"), "2026-01-02", "2026-01-09",
                       "2026-01-05", Decimal("15"))],
    )
    resumo = fonte_com(conexao).sondar("rec")
    ano, de, ate, cal, quantas = resumo["ano_discordante"][0]
    assert (ano, quantas) == (Decimal("2025"), Decimal("15"))
    assert de.startswith("2026"), "o caso de borda: ano_solic atrasado na virada"

    # e sem discordancia, a consulta de detalhe nao roda
    limpa = ConexaoFalsa(
        "rec",
        linhas=[linha_nativa("rec")],
        resumo=_resumo_falso(36592, 36592),
        identidade=(Decimal("36592"),) * 7 + (Decimal("0"),),
    )
    assert fonte_com(limpa).sondar("rec")["ano_discordante"] == []
    assert not any("GROUP BY ANO_SOLIC" in sql for sql, _ in limpa.executados), (
        "a consulta de detalhe so roda quando a contagem acusou discordancia"
    )


def test_sondar_nao_pergunta_por_colisao_quando_a_chave_e_unica():
    """Consulta com `GROUP BY ... HAVING` sobre a tabela inteira nao se roda por
    esporte: ela so acontece quando a contagem provou que ha o que olhar."""
    conexao = ConexaoFalsa(
        "rec",
        linhas=[linha_nativa("rec")],
        resumo=_resumo_falso(36592, 36592),
        identidade=(Decimal("36592"),) * 7 + (Decimal("0"),),
    )
    resumo = fonte_com(conexao).sondar("rec")
    assert resumo["colisoes"] == []
    assert not any("HAVING" in sql.upper() for sql, _ in conexao.executados)


def test_chave_concatenada_sai_do_contrato_e_protege_nulo():
    """A expressao e gerada de `CHAVE_NATURAL` -- lista escrita a mao aqui
    divergiria do upsert sem ninguem notar. `NVL` porque um nulo colapsaria a
    chave inteira e a medicao erraria para BAIXO justamente quando o dado
    piorou; `CHR(31)` porque um valor com o separador dentro inventaria
    duplicata."""
    for movimento in contrato.MOVIMENTOS:
        sql = fonte_oracle.sql_identidade(movimento)
        for coluna in contrato.CHAVE_NATURAL:
            nome = contrato.coluna_dw(coluna, movimento)
            assert f"NVL(TO_CHAR({nome}), ' ')" in sql, f"{movimento}: {nome}"
        assert sql.count("CHR(31)") >= len(contrato.CHAVE_NATURAL) - 1
        assert "'|'" not in sql, "separador tem que ser impossivel no dado"


def test_candidatos_de_identidade_vao_do_mais_grosso_ao_mais_fino():
    """A ordem nao e estetica, e a regra de decisao. Identidade fina significa
    que correcao na coluna extra deixa de ser update e passa a ser INSERT, com a
    linha antiga sobrevivendo ao lado -- numero dobrado, sem alarme."""
    rotulos = [r for r, _e in fonte_oracle.CANDIDATOS_DE_IDENTIDADE]
    assert rotulos == [
        "chave de hoje", "+ ano de data_solic", "+ ano_solic",
        "+ ano de nk_calendario", "+ data_solic", "+ nk_calendario",
    ], (
        "entre dois candidatos de mesma granularidade vem primeiro o derivado da "
        "coluna que o fato carrega como data, e nao o da copia denormalizada"
    )
    sql = fonte_oracle.sql_identidade("rec")
    assert sql.index("TO_CHAR(ANO_SOLIC)") < sql.index("'YYYY-MM-DD'"),         "o ano tem que ser medido antes da data inteira"
    # e a conferencia de que escolher ano_solic e legitimo: ele tem que
    # concordar com o ano de data_solic, e isso e medido, nao suposto
    assert "EXTRACT(YEAR FROM DATA_SOLIC)" in sql


# =================================================== somente leitura
_PALAVRAS_DE_ESCRITA = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "DROP", "CREATE",
    "ALTER", "GRANT", "REVOKE", "COMMIT",
)
_METODOS_DE_ESCRITA = {"commit", "rollback", "executemany", "setinputsizes"}


def _arvore_do_modulo():
    caminho = pathlib.Path(fonte_oracle.__file__)
    return ast.parse(caminho.read_text(encoding="utf-8"))


def _docstrings(arvore):
    """Toda docstring do modulo, para a guarda ignorar prosa."""
    encontradas = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)):
            texto = ast.get_docstring(no, clean=False)
            if texto is not None:
                encontradas.add(texto)
    return encontradas


def test_guarda_estatica_nenhum_literal_do_modulo_escreve():
    """A estatica pega o codigo que nenhum teste exercitou. Ela olha literal, e
    nao a prosa: docstring fala de escrita para explicar por que nao ha."""
    arvore = _arvore_do_modulo()
    prosa = _docstrings(arvore)
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
            continue
        if no.value in prosa:
            continue
        for palavra in _PALAVRAS_DE_ESCRITA:
            assert not re.search(rf"\b{palavra}\b", no.value, re.IGNORECASE), (
                f"literal do fonte_oracle.py com palavra de escrita "
                f"({palavra}): {no.value!r}"
            )


def test_guarda_estatica_nenhuma_chamada_de_escrita_no_driver():
    """`commit`/`rollback` num modulo que so le sao sinal de que alguem passou a
    escrever por aqui. `executemany` e escrita em lote."""
    chamados = {
        no.func.attr
        for no in ast.walk(_arvore_do_modulo())
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
    }
    assert not (chamados & _METODOS_DE_ESCRITA), \
        f"chamada de escrita no fonte_oracle.py: {sorted(chamados & _METODOS_DE_ESCRITA)}"


def test_guarda_de_runtime_todo_comando_emitido_e_select():
    """A de runtime pega o comando montado por concatenacao, que a estatica nao
    veria. Exercita os dois caminhos que emitem SQL."""
    conexao = ConexaoFalsa(
        "exp",
        linhas=[linha_nativa("exp")],
        resumo=_resumo_falso(42789, 42639),
    )
    fonte = fonte_com(conexao)
    list(fonte.extrair("exp", datetime(2026, 8, 20)))
    fonte.sondar("exp")

    assert conexao.executados, "o teste nao exercitou nada"
    for sql, _binds in conexao.executados:
        assert sql.lstrip().upper().startswith("SELECT"), sql


def test_piso_de_periodo_vale_em_toda_rodada():
    """O recorte da Maria (25/ago/2026): a V3 le de 2026 para frente.

    Vale na carga completa e na incremental -- sao perguntas diferentes: o piso e
    ESCOPO (que periodo interessa), o `desde` e FRESCOR (o que mudou desde a
    ultima rodada). Confundir os dois faria a carga completa trazer 2023."""
    for movimento in contrato.MOVIMENTOS:
        for desde in (None, datetime(2026, 8, 25, 13, 48)):
            sql, binds = fonte_oracle.sql_select(movimento, desde)
            assert "NK_CALENDARIO >= :piso" in sql, f"{movimento}/{desde}"
            assert binds["piso"] == contrato.piso_do_periodo()
            assert "2026-01-01" not in sql, "o piso vai por bind, nao concatenado"


def test_piso_configuravel_muda_o_bind_e_nao_o_sql(monkeypatch):
    """A Maria nomeou o caso de uso ao decidir: comparar 2025 com 2026 um dia.
    Trocar o piso e uma variavel de ambiente -- e o SQL nem muda, porque o valor
    viaja como parametro. Consulta que muda de texto por configuracao perde o
    plano em cache e some do log agrupado."""
    sql_padrao, binds_padrao = fonte_oracle.sql_select("rec")
    monkeypatch.setenv(contrato.ENV_ANO_MINIMO, "2025")
    sql_outro, binds_outro = fonte_oracle.sql_select("rec")

    assert sql_outro == sql_padrao
    assert binds_padrao["piso"] == date(2026, 1, 1)
    assert binds_outro["piso"] == date(2025, 1, 1)


def test_piso_vale_tambem_para_medir_identidade():
    """A medicao tem que descrever o que a carga GRAVA.

    Sem o piso, a identidade seria medida na tabela inteira e acusaria as 27.834
    colisoes de 2023-2025 num recorte que nao le 2023 -- alarme sobre dado que
    nao entra. Quem quiser saber se a chave aguenta um periodo maior baixa o
    `DW_ANO_MINIMO` e roda o sondar de novo, que e o fluxo certo ANTES de
    ampliar a janela."""
    for gerador in (fonte_oracle.sql_identidade, fonte_oracle.sql_colisoes,
                    fonte_oracle.sql_ano_discordante):
        assert "NK_CALENDARIO >= :piso" in gerador("rec"), gerador.__name__


def test_ano_minimo_invalido_nao_gera_sql(monkeypatch):
    """Ano digitado errado nao pode virar "carrega tudo" nem "carrega nada"."""
    for ruim in ("26", "20226", "dois mil e vinte e seis", "2026.5"):
        monkeypatch.setenv(contrato.ENV_ANO_MINIMO, ruim)
        with pytest.raises(contrato.AnoMinimoInvalido, match=contrato.ENV_ANO_MINIMO):
            fonte_oracle.sql_select("rec")


# ================================================= rodada de verdade
def test_rodada_registra_o_nome_qualificado_e_a_fonte_oracle(banco_migrado):
    """Uma carga completa com driver falso, ponta a ponta: o carregador nao
    soube que a fonte mudou, e `cat_cargas` guarda de onde o numero veio.

    O nome qualificado em `tabela_origem` e o que a Maria autorizou invalidar: a
    marca d'agua e chaveada por ele, entao a primeira rodada depois deste lote e
    completa de proposito."""
    conexao = ConexaoFalsa("rec", linhas=[
        linha_nativa("rec", num_gem="0000000001"),
        linha_nativa("rec", num_gem="0000000002",
                     dw_data_alteracao=datetime(2026, 8, 24, 17, 46, 39)),
    ])
    resultado = carregar_movimento(fonte_com(conexao), "rec")

    assert (resultado.status, resultado.inseridas) == ("ok", 2)
    assert resultado.max_dw_data_alteracao == datetime(2026, 8, 24, 17, 46, 39)

    linha = consultar(
        "SELECT tabela_origem, fonte, status, linhas_lidas, max_dw_data_alteracao,"
        " janela_de, janela_ate FROM cat_cargas ORDER BY id DESC LIMIT 1"
    )[0]
    assert linha[0] == "DM_VOLUMETRIA.FATO_VOL_REC_CAT_V01"
    assert linha[1] == "oracle", "a 0020 existe para responder de onde o numero veio"
    assert (linha[2], linha[3]) == ("ok", 2)
    assert linha[4] == datetime(2026, 8, 24, 17, 46, 39)
    # janela_* sao DATE e significam janela de data de NEGOCIO relida; o
    # incremento daqui e por timestamp de processamento, que ja esta inteiro em
    # max_dw_data_alteracao. Preencher com a data truncada misturaria os dois.
    assert (linha[5], linha[6]) == (None, None)

    # e a marca d'agua passa a ser encontravel pelo nome novo
    assert destino.marca_dagua("rec") == datetime(2026, 8, 24, 17, 46, 39)
    assert destino.tabela_origem("rec") == contrato.tabela("rec")


def test_tabela_ausente_derruba_a_rodada_e_fica_no_historico(banco_migrado):
    """`ORA-00942` responde a mesma coisa para "nao existe" e para "existe e
    voce nao pode ver" -- entao a mensagem tem que sobreviver no historico, e
    nao virar so um traceback no console de quem nao estava olhando."""
    conexao = ConexaoFalsa(
        "rec", erro=RuntimeError("ORA-00942: table or view does not exist")
    )
    with pytest.raises(RuntimeError, match="ORA-00942"):
        carregar_movimento(fonte_com(conexao), "rec")

    linha = consultar(
        "SELECT status, fonte, erro FROM cat_cargas ORDER BY id DESC LIMIT 1"
    )[0]
    assert linha[0] == "erro"
    assert linha[1] == "oracle"
    assert "ORA-00942" in linha[2]
    assert consultar("SELECT count(*) FROM cat_fato_recebimento")[0][0] == 0
