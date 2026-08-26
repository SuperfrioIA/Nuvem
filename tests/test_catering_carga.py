"""V3.1 -- o carregador: coercao, contrato, idempotencia e registro de rodada.

## Como esta suite esta dividida, e por que

**Sem banco** (a maioria): coercao e contrato sao funcoes puras, e o que elas
garantem -- zero a esquerda preservado, medida vazia virando NULL e nao zero,
numero invalido virando erro e nao zero -- e barato de testar e caro de
descobrir quebrado em producao.

**Com Postgres real** (cinco testes): a fixture `banco_migrado` zera o schema e
roda as 20 migrations a cada teste, entao cada teste de banco custa uma cadeia
completa de migration. Por isso eles sao agrupados por historia, no mesmo
padrao do `test_catering_schema.py`: cada assert carrega mensagem propria, e a
falha continua dizendo o que quebrou.

## O teste que prova o V3.5

`test_coercao_aceita_texto_e_valor_nativo` e o que sustenta a promessa de que
o Oracle entra como adaptador e nao como reescrita. O CSV entrega
`'25290.217'` e `'2026-01-05 00:00:00.000'`; o `oracledb` entrega `Decimal` e
`datetime` para as MESMAS colunas. Se os dois nao passarem pelo mesmo funil
com o mesmo resultado, a troca da fonte deixa de ser uma classe e volta a ser
uma reescrita -- e ninguem descobre isso ate o V3.5.

## O teste dos CSVs de verdade PULA quando o dado nao esta na maquina

`docs/Analise/` e gitignored de proposito: dado real de operacao nao vai pro
Git. Entao o teste de fidelidade total (36.300 e 42.468 linhas, as 6 unidades,
os 40 nomes de estoque, as 14 raizes de cliente) roda na maquina onde a
extracao existe e pula, dizendo por que, onde ela nao existe. Fingir que passou
seria pior; falhar por dado ausente transformaria a suite em alarme falso.
"""

import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from catering import contrato
from catering.carga import carregar_movimento, carregar_tudo, destino, dimensoes
from catering.carga import transformacao as tr
from catering.carga.fonte_csv import FonteCSV
from catering.dominio import tipo_estoque
from tests.conftest import consultar

# --------------------------------------------------------------- medido
# Numeros das extracoes de 21/ago/2026, medidos antes de escrever o codigo.
DIRETORIO_DW = Path(__file__).resolve().parent.parent / "docs" / "Analise"
# O que a fonte ENTREGA com o piso de periodo de 2026 (contrato.piso_do_periodo).
# Os arquivos tem 36.300 e 42.468 linhas; as 150 linhas de diferenca na
# expedicao sao **dez/2025** (128,7 t solicitadas), que saem da janela pela
# decisao da Maria de 25/ago/2026 -- a V3 le de 2026 para frente. O recebimento
# nao tem linha anterior a 2026, entao ele nao muda.
NO_ARQUIVO = {"rec": 36_300, "exp": 42_468}
LINHAS = {"rec": 36_300, "exp": 42_318}
FORA_DA_JANELA = {"rec": 0, "exp": 150}
UNIDADES = 6
NOMES_ESTOQUE = 40
RAIZES_CLIENTE = 14
RAIZES_COM_VARIAS_GRAFIAS = 7
# A guia de recebimento cancelada: 4 celulas vazias em 36.300 linhas.
GUIA_CANCELADA = "0000000609"

tem_extracao = pytest.mark.skipif(
    not (DIRETORIO_DW / "dm_volumetriaRecebimento.csv").exists(),
    reason=(
        "docs/Analise/ e gitignored (dado real de operacao nao vai pro Git). "
        "Este teste roda onde a extracao de 21/ago/2026 existe."
    ),
)


# ------------------------------------------------------- fonte sintetica
# Valores validos por tipo do contrato, para montar linha crua sem depender
# do arquivo de 34 MB.
_PADRAO_POR_TIPO = {
    "TEXT": "X",
    "INTEGER": "1",
    "SMALLINT": "2026",
    "NUMERIC(18,3)": "10.500",
    "DATE": "2026-01-05 00:00:00.000",
    "TIMESTAMP": "2026-08-20 15:26:39.000",
}

# Colunas cujo valor precisa ser plausivel, nao so do tipo certo: a instancia
# tem que ser SLIN (escopo), e os identificadores tem zero a esquerda.
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


def linha_crua(movimento, **sobrescritas):
    """Linha valida com as chaves em MAIUSCULAS, como o DW as nomeia.

    As sobrescritas usam os nomes das NOSSAS colunas (minusculas), que e como
    se pensa sobre elas -- a traducao pro nome do DW sai do contrato."""
    linha = {}
    for nome, tipo, _nulo in contrato.colunas(movimento):
        valor = _PADRAO.get(nome, _PADRAO_POR_TIPO[tipo])
        linha[contrato.coluna_dw(nome, movimento)] = valor
    for nome, valor in sobrescritas.items():
        linha[contrato.coluna_dw(nome, movimento)] = valor
    return linha


class FonteFalsa:
    """Fonte em memoria com a MESMA interface da `FonteCSV`. Existe para provar
    que `transformar` e `gravar` nao sabem de onde a linha veio -- se algum dos
    dois espiasse a fonte, esta classe nao funcionaria."""

    nome = "csv"

    def __init__(self, por_movimento):
        self.por_movimento = por_movimento

    def descrever(self, movimento):
        return f"fonte sintetica ({len(self.por_movimento.get(movimento, []))} linha(s))"

    def extrair(self, movimento, desde=None):
        for linha in self.por_movimento.get(movimento, []):
            if desde is not None:
                alterada = tr.instante(
                    linha.get(contrato.coluna_dw("dw_data_alteracao", movimento))
                )
                if alterada is None or alterada <= desde:
                    continue
            yield linha


def _cargas():
    return consultar(
        "SELECT id, tabela_origem, fonte, status, linhas_lidas, linhas_inseridas,"
        " linhas_atualizadas, max_dw_data_alteracao, erro"
        " FROM cat_cargas ORDER BY id"
    )


def _contar(tabela):
    return consultar(f"SELECT count(*) FROM {tabela}")[0][0]


# ============================================================== coercao
def test_identificador_com_zero_a_esquerda_continua_texto():
    """O achado 2 do contrato. Como inteiro, `0000000609` viraria 609 e
    deixaria de casar com a fonte -- quebra o de-para inteiro."""
    assert tr.texto("0000000609") == "0000000609"
    assert tr.texto('"02060862000569"') == '"02060862000569"', (
        "aspas nao devem ser removidas aqui: o leitor de CSV ja as tirou, e "
        "tirar de novo corromperia valor que legitimamente as tenha"
    )
    linha = tr.transformar(linha_crua("rec", num_gem="0000000035"), "rec")
    assert linha["num_gem"] == "0000000035"
    assert linha["nk_slin_filial"] == "001"


def test_medida_vazia_vira_nulo_e_nao_zero():
    """A guia cancelada. `NULL` mantem "cancelada" distinguivel de "pesou
    zero"; virar `0` apagaria uma das limitacoes que a tela tem que declarar."""
    linha = tr.transformar(
        linha_crua("rec", qtde_vol2="", qtde_peso2="", qtde_pbrt2="", qtde_vlr=""),
        "rec",
    )
    for coluna in ("qtde_vol2", "qtde_peso2", "qtde_pbrt2", "qtde_vlr"):
        assert linha[coluna] is None, f"{coluna} deveria ser NULL, veio {linha[coluna]!r}"
    assert linha["qtde_sku"] is not None, "sku nao esta vazio nessa linha"


def test_numero_invalido_e_erro_e_nunca_zero():
    """O `num()` do artefato devolve 0.0 aqui. Atalho aceitavel em laboratorio,
    inaceitavel num carregador: viraria peso faltando sem ninguem notar."""
    with pytest.raises(tr.LinhaInvalida, match="numero invalido"):
        tr.numero("mil e quinhentos")
    with pytest.raises(tr.LinhaInvalida, match="inteiro invalido"):
        tr.inteiro("varios")
    with pytest.raises(tr.LinhaInvalida, match="data/hora invalida"):
        tr.dia("05/01/2026")
    with pytest.raises(tr.LinhaInvalida, match="fracionario"):
        tr.inteiro(Decimal("1.5"))
    # A mensagem tem que dizer QUAL coluna, senao achar a celula num arquivo de
    # 36 mil linhas custa uma investigacao.
    with pytest.raises(tr.LinhaInvalida, match="qtde_peso2"):
        tr.transformar(linha_crua("rec", qtde_peso2="x"), "rec")


def test_coercao_aceita_texto_e_valor_nativo():
    """O teste que sustenta o V3.5: o CSV entrega texto, o `oracledb` entrega
    `datetime`/`Decimal` para as MESMAS colunas, e os dois tem que passar pelo
    mesmo funil com o mesmo resultado. Sem isto, trocar a fonte deixa de ser
    uma classe nova e volta a ser reescrita."""
    assert tr.dia("2026-01-05 00:00:00.000") == date(2026, 1, 5)
    assert tr.dia(datetime(2026, 1, 5, 0, 0)) == date(2026, 1, 5)
    assert tr.dia(date(2026, 1, 5)) == date(2026, 1, 5)

    assert tr.instante("2026-08-20 15:26:39.000") == datetime(2026, 8, 20, 15, 26, 39)
    assert tr.instante(datetime(2026, 8, 20, 15, 26, 39)) == datetime(2026, 8, 20, 15, 26, 39)

    assert tr.numero("25290.217") == Decimal("25290.217")
    assert tr.numero(Decimal("25290.217")) == Decimal("25290.217")
    assert tr.inteiro("1045") == 1045
    assert tr.inteiro(Decimal("1045")) == 1045

    # A linha inteira pelos dois caminhos tem que dar no mesmo lugar.
    do_texto = tr.transformar(linha_crua("rec"), "rec")
    nativa = tr.transformar(
        linha_crua(
            "rec",
            nk_calendario=date(2026, 1, 5),
            dw_data_inclusao=datetime(2026, 8, 20, 15, 26, 39),
            dw_data_alteracao=datetime(2026, 8, 20, 15, 26, 39),
            data_solic=date(2026, 1, 5),
            dthr_confirm=datetime(2026, 8, 20, 15, 26, 39),
            pk_dw=1,
            ano_solic=2026,
            qtde_peso2=Decimal("10.500"),
        ),
        "rec",
    )
    assert do_texto == nativa


def test_vazio_em_coluna_obrigatoria_derruba():
    """`NOT NULL` no contrato significa PREENCHIDO, nao apenas nao-nulo:
    `nk_wms_filial = ''` passaria no constraint do banco e viraria unidade
    fantasma em `cat_unidades`."""
    with pytest.raises(tr.LinhaInvalida, match="nk_wms_filial"):
        tr.transformar(linha_crua("rec", nk_wms_filial=""), "rec")
    with pytest.raises(tr.LinhaInvalida, match="obrigatoria"):
        tr.transformar(linha_crua("exp", nk_calendario=""), "exp")


def test_booleano_nao_passa_por_numero():
    """`True` e `int` em Python e passaria calado como 1. Peso `True` seria um
    numero inventado."""
    with pytest.raises(tr.LinhaInvalida, match="booleano"):
        tr.inteiro(True)
    with pytest.raises(tr.LinhaInvalida, match="booleano"):
        tr.numero(False)


# ============================================================= contrato
def test_contrato_recusa_coluna_faltando_e_coluna_sobrando():
    """Nos dois sentidos: coluna que falta quebraria adiante com erro obscuro,
    e coluna que sobra e coluna que o carregador nao grava."""
    completas = list(tr.colunas_dw("rec"))

    with pytest.raises(tr.ContratoDivergente, match="QTDE_PESO2"):
        tr.conferir_colunas([c for c in completas if c != "QTDE_PESO2"], "rec")

    with pytest.raises(tr.ContratoDivergente, match="QTDE_NOVA"):
        tr.conferir_colunas(completas + ["QTDE_NOVA"], "rec")

    tr.conferir_colunas(completas, "rec")   # o cabecalho certo passa


def test_escopo_e_a_instancia_slin():
    """Catering = instancia SLIN. As outras instancias do DW sao outro negocio
    -- pular e o certo, e nao derruba a rodada."""
    assert tr.dentro_do_escopo(linha_crua("rec")) is True
    assert tr.dentro_do_escopo(linha_crua("rec", nk_instancia="DISTROMAQ_PRD")) is False
    assert tr.dentro_do_escopo(linha_crua("rec", nk_instancia="")) is False


# ================================================================ fonte
@tem_extracao
def test_fonte_csv_le_as_duas_extracoes():
    fonte = FonteCSV(DIRETORIO_DW)
    for movimento, esperado in LINHAS.items():
        linhas = sum(1 for _ in fonte.extrair(movimento))
        assert linhas == esperado, f"{movimento}: contagem divergiu do medido"


@tem_extracao
def test_fonte_csv_nao_escreve_na_fonte():
    """Fonte nao se escreve -- a mesma disciplina do SharePoint do DataHub."""
    fonte = FonteCSV(DIRETORIO_DW)
    antes = {
        movimento: fonte.caminho(movimento).stat() for movimento in ("rec", "exp")
    }
    for movimento in ("rec", "exp"):
        for _ in fonte.extrair(movimento):
            pass
    for movimento, estado in antes.items():
        agora = fonte.caminho(movimento).stat()
        assert agora.st_mtime == estado.st_mtime, f"{movimento}: mtime mudou"
        assert agora.st_size == estado.st_size, f"{movimento}: tamanho mudou"


def test_fonte_csv_reclama_de_arquivo_ausente(tmp_path):
    with pytest.raises(FileNotFoundError, match="dm_volumetriaRecebimento"):
        list(FonteCSV(tmp_path).extrair("rec"))


def test_desde_filtra_por_data_de_alteracao():
    """O `desde` ja esta na assinatura para o V3.5 nao mexer em assinatura de
    ninguem. Maior, nao maior-ou-igual: igual e a linha que a rodada anterior
    ja carregou."""
    velha = linha_crua("rec", num_gem="0000000001",
                       dw_data_alteracao="2026-08-20 10:00:00.000")
    nova = linha_crua("rec", num_gem="0000000002",
                      dw_data_alteracao="2026-08-21 10:00:00.000")
    fonte = FonteFalsa({"rec": [velha, nova]})

    assert len(list(fonte.extrair("rec"))) == 2
    corte = datetime(2026, 8, 20, 10, 0, 0)
    devolvidas = list(fonte.extrair("rec", desde=corte))
    assert len(devolvidas) == 1
    assert devolvidas[0][contrato.coluna_dw("num_gem", "rec")] == "0000000002"


# ================================================== carga (banco real)
def test_upsert_insere_atualiza_e_ignora_linha_igual(banco_migrado):
    """O ciclo de vida do upsert numa historia so, porque cada teste de banco
    custa a cadeia inteira de migrations.

    O que esta sendo fixado: `linhas_atualizadas` significa "o conteudo mudou",
    nao "a linha reapareceu". Update incondicional reportaria tudo atualizado
    em toda rodada e esconderia mudanca real."""
    uma = linha_crua("rec", num_gem="0000000001", qtde_peso2="100.000")
    outra = linha_crua("rec", num_gem="0000000002", qtde_peso2="200.000")

    # 1. primeira carga: as duas entram
    resultado = carregar_movimento(FonteFalsa({"rec": [uma, outra]}), "rec")
    assert (resultado.status, resultado.inseridas, resultado.atualizadas) == ("ok", 2, 0)
    assert _contar("cat_fato_recebimento") == 2
    primeira_carga = resultado.carga_id

    # 2. a MESMA fonte de novo: nada inserido, nada atualizado, nada tocado
    repetida = carregar_movimento(FonteFalsa({"rec": [uma, outra]}), "rec")
    assert (repetida.inseridas, repetida.atualizadas) == (0, 0), \
        "rodar duas vezes sobre a mesma fonte tem que ser inocuo"
    assert repetida.iguais == 2
    assert _contar("cat_fato_recebimento") == 2
    donos = consultar("SELECT DISTINCT carga_id FROM cat_fato_recebimento")
    assert donos == [(primeira_carga,)], \
        "linha sem mudanca nao pode ter o carga_id mexido"

    # 3. peso diferente na mesma chave natural: uma atualizada, e so uma
    mudada = linha_crua("rec", num_gem="0000000001", qtde_peso2="150.000",
                        dw_data_alteracao="2026-08-21 09:00:00.000")
    terceira = carregar_movimento(FonteFalsa({"rec": [mudada, outra]}), "rec")
    assert (terceira.inseridas, terceira.atualizadas, terceira.iguais) == (0, 1, 1)
    assert _contar("cat_fato_recebimento") == 2
    assert consultar(
        "SELECT qtde_peso2, carga_id FROM cat_fato_recebimento WHERE num_gem = '0000000001'"
    ) == [(Decimal("150.000"), terceira.carga_id)]

    # 4. chave natural nova: entra sem tocar nas outras
    nova = linha_crua("rec", num_gem="0000000003")
    quarta = carregar_movimento(FonteFalsa({"rec": [mudada, outra, nova]}), "rec")
    assert (quarta.inseridas, quarta.atualizadas, quarta.iguais) == (1, 0, 2)
    assert _contar("cat_fato_recebimento") == 3

    # 5. o historico das rodadas, com a marca d'agua de onde o V3.5 retoma
    cargas = _cargas()
    assert [c[3] for c in cargas] == ["ok"] * 4
    assert {c[2] for c in cargas} == {"csv"}, "a fonte da rodada tem que ficar registrada"
    assert destino.marca_dagua("rec") == datetime(2026, 8, 21, 9, 0, 0)


def test_linha_invalida_derruba_a_rodada_inteira(banco_migrado):
    """Decisao da Maria, 24/ago/2026. E o que a decisao protege: o dado da
    rodada ANTERIOR continua no banco, entao falhar custa frescor, nao dado --
    enquanto carga parcial custaria um furo silencioso permanente."""
    boa = linha_crua("rec", num_gem="0000000001")
    carregar_movimento(FonteFalsa({"rec": [boa]}), "rec")
    assert _contar("cat_fato_recebimento") == 1

    # tres linhas, a ultima quebrada: nenhuma das tres pode entrar
    lote = [
        linha_crua("rec", num_gem="0000000002"),
        linha_crua("rec", num_gem="0000000003"),
        linha_crua("rec", num_gem="0000000004", nk_wms_filial=""),
    ]
    with pytest.raises(tr.LinhaInvalida) as erro:
        carregar_movimento(FonteFalsa({"rec": lote}), "rec")

    assert "nk_wms_filial" in str(erro.value), "a mensagem tem que nomear a coluna"
    assert "linha 3" in str(erro.value), "e dizer qual linha da fonte"

    assert _contar("cat_fato_recebimento") == 1, \
        "rollback: nenhuma linha do lote que falhou pode ter entrado"

    ultima = _cargas()[-1]
    assert ultima[3] == "erro"
    assert "nk_wms_filial" in ultima[8], \
        "o registro da falha tem que sobreviver ao rollback, com a mensagem"


def test_fora_de_escopo_e_pulado_e_incremental_vazio_e_sem_dado(banco_migrado):
    """Duas linhas que nao entram, por motivos diferentes. Fora de escopo e
    outro negocio (nao derruba); incremental vazio e o caso normal do dia a
    dia."""
    dentro = linha_crua("rec", num_gem="0000000001")
    fora = linha_crua("rec", num_gem="0000000002", nk_instancia="DISTROMAQ_PRD")

    resultado = carregar_movimento(FonteFalsa({"rec": [dentro, fora]}), "rec")
    assert resultado.status == "ok"
    assert (resultado.linhas_fonte, resultado.linhas_carregadas) == (2, 1)
    assert resultado.fora_escopo == 1
    assert _contar("cat_fato_recebimento") == 1

    # `linhas_lidas` conta o que entrou na carga, para que
    # lidas - inseridas - atualizadas continue sendo exatamente as iguais
    assert _cargas()[-1][4] == 1

    marca = destino.marca_dagua("rec")
    vazia = carregar_movimento(FonteFalsa({"rec": []}), "rec", desde=marca)
    assert vazia.status == "sem_dado"
    assert _cargas()[-1][3] == "sem_dado"
    # rodada sem dado nao pode virar marca d'agua: o incremento seguinte
    # retomaria do lugar errado
    assert destino.marca_dagua("rec") == datetime(2026, 8, 20, 15, 26, 39)


def test_mesmo_gem_em_anos_diferentes_convive(banco_migrado):
    """A regressao da primeira carga real (25/ago/2026).

    O DW reconstruiu a tabela com 2023-2026 e a carga morreu com `ON CONFLICT DO
    UPDATE command cannot affect row a second time`: `num_gem` se recicla por
    ano, e a chave natural de seis colunas nao tinha ano. Repetia em 27.834
    linhas de 201.848 no recebimento.

    Este teste e o mesmo cenario em miniatura -- a MESMA guia em quatro anos, no
    mesmo lote, como a fonte a entrega. Sem `ano_solic` na identidade ele morre
    exatamente como a producao morreu."""
    quatro_anos = [
        linha_crua(
            "rec",
            num_gem="0000000020",
            ano_solic=str(ano),
            data_solic=f"{ano}-01-03 00:00:00.000",
            nk_calendario=f"{ano}-01-03 00:00:00.000",
        )
        for ano in (2023, 2024, 2025, 2026)
    ]
    resultado = carregar_movimento(FonteFalsa({"rec": quatro_anos}), "rec")

    assert (resultado.status, resultado.inseridas) == ("ok", 4),         "as quatro sao guias distintas: mesmo numero, anos diferentes"
    assert consultar(
        "SELECT ano_solic FROM cat_fato_recebimento"
        " WHERE num_gem = '0000000020' ORDER BY ano_solic"
    ) == [(2023,), (2024,), (2025,), (2026,)]

    # e a idempotencia continua valendo com a chave nova: reapresentar as
    # mesmas quatro nao mexe em nada
    de_novo = carregar_movimento(FonteFalsa({"rec": quatro_anos}), "rec")
    assert (de_novo.inseridas, de_novo.atualizadas, de_novo.iguais) == (0, 0, 4)

    # E a mesma chave com conteudo DIFERENTE no mesmo lote segue sendo alarme --
    # foi assim que a producao morreu: a segunda linha tentava atualizar a que a
    # primeira acabara de inserir. Chave nova de proposito, e o paragrafo abaixo
    # explica por que isso importa.
    nova = linha_crua("rec", num_gem="0000000021", ano_solic="2023",
                      data_solic="2023-01-03 00:00:00.000",
                      nk_calendario="2023-01-03 00:00:00.000")
    divergente = dict(nova)
    divergente[contrato.coluna_dw("qtde_peso2", "rec")] = "999.000"
    with pytest.raises(Exception, match="affect row a second time"):
        carregar_movimento(FonteFalsa({"rec": [nova, divergente]}), "rec")


def test_o_alarme_de_chave_repetida_tem_um_furo_conhecido(banco_migrado):
    """Limite do alarme, medido em 25/ago/2026 -- fixado aqui para ninguem
    acreditar que ele e total.

    O `ON CONFLICT DO UPDATE` so grita ("cannot affect row a second time")
    quando duas linhas do mesmo lote realmente ESCREVEM na mesma linha. O
    `WHERE ... IS DISTINCT FROM` (que existe para `linhas_atualizadas` significar
    o que diz) faz uma linha identica a do banco nao afetar nada -- e nesse caso
    a companheira divergente escreve sozinha, sem alarme, e vence.

    Para o furo aparecer e preciso a conjuncao: a fonte publicar a mesma chave
    duas vezes com conteudo diferente, E uma das duas ser byte a byte igual ao
    que ja esta gravado -- inclusive `pk_dw` e `dw_data_alteracao`, que mudam
    sempre que o DW reconstroi ou toca a linha. Ou seja: so acontece com linha
    que o DW nao tocou desde a nossa ultima carga.

    Nao foi fechado, e a razao e custo: fechar exige guardar a chave de cada
    linha da rodada em memoria (uma pagina nao basta, porque a repeticao pode
    cair entre paginas) -- ~80 MB para 232 mil linhas -- ou trocar por hash e
    aceitar alarme falso. O estado que sobra e defensavel (a linha divergente
    vence, e nenhuma medida se perde), e um furo escrito e melhor que um alarme
    em que se confia sem saber onde ele nao alcanca."""
    linha = linha_crua("rec", num_gem="0000000777", ano_solic="2024",
                       data_solic="2024-03-01 00:00:00.000",
                       nk_calendario="2024-03-01 00:00:00.000")
    primeira = carregar_movimento(FonteFalsa({"rec": [linha]}), "rec")
    assert primeira.inseridas == 1

    divergente = dict(linha)
    divergente[contrato.coluna_dw("qtde_peso2", "rec")] = "999.000"
    # a identica nao afeta nada; a divergente escreve sozinha -> sem alarme
    passou = carregar_movimento(FonteFalsa({"rec": [linha, divergente]}), "rec")
    assert (passou.status, passou.atualizadas) == ("ok", 1)
    assert consultar(
        "SELECT qtde_peso2 FROM cat_fato_recebimento WHERE num_gem = '0000000777'"
    ) == [(Decimal("999.000"),)], "a divergente venceu, e em silencio"


def test_carga_completa_vazia_e_erro_e_nao_sem_dado(banco_migrado):
    """V3.5, A-7: a carga nunca pode reportar desfecho normal com zero linha.

    `sem_dado` e certo no incremental (nada mudou no DW) e errado numa carga
    COMPLETA -- ali ele significa a fonte inteira vindo vazia, com a tela
    seguindo em frente com o dado velho e ninguem avisado. Tabela ausente ja
    derruba sozinha com `ORA-00942`; esta guarda cobre o caso pior, a tabela
    que existe e vem vazia porque o DW reconstroi objeto.

    Os dois motivos possiveis produzem mensagens diferentes de proposito: "a
    fonte nao devolveu linha" e um problema no DW ou no acesso; "todas fora do
    escopo" e a instancia ter mudado, que e problema de negocio."""
    from catering.carga import CargaVazia

    with pytest.raises(CargaVazia, match="nao devolveu linha nenhuma"):
        carregar_movimento(FonteFalsa({"rec": []}), "rec")

    ultima = _cargas()[-1]
    assert ultima[3] == "erro", "a rodada vazia tem que ficar no historico"
    assert "nenhuma linha" in ultima[8]
    assert destino.marca_dagua("rec") is None,         "rodada que falhou nao pode virar marca d'agua"

    # o outro motivo: a fonte trouxe linha, mas nenhuma e do catering
    fora = linha_crua("rec", nk_instancia="DISTROMAQ_PRD")
    with pytest.raises(CargaVazia, match="fora do escopo"):
        carregar_movimento(FonteFalsa({"rec": [fora]}), "rec")
    assert _contar("cat_fato_recebimento") == 0


def test_dimensoes_guardam_as_nossas_decisoes(banco_migrado):
    """As tres dimensoes: a excecao da sigla, o tipo de estoque com a regra que
    decidiu, e o cliente canonizado. E que rodar de novo nao duplica."""
    linhas = [
        # a unica excecao de sigla: o DW manda RMSPV, a tela mostra RMSPIV
        linha_crua("rec", num_gem="0000000001", nk_wms_filial="RMSPV",
                   nome_und="RMSPIV - SANCA", nome_estoque="CONG FLV (CUCINARE)",
                   nk_cliente="67945071", raz_social="SAPORE S.A",
                   qtde_peso2="100.000"),
        # a mesma raiz com outra grafia, com peso MENOR: nao deve ganhar
        linha_crua("rec", num_gem="0000000002", nome_estoque="AGUA / CARVAO",
                   nk_cliente="67945071", raz_social="SAPORE S A",
                   qtde_peso2="10.000"),
        linha_crua("rec", num_gem="0000000003", nome_estoque="CONSOLIDADOR",
                   nk_cliente="05599283", raz_social="CONVIDA REFEICOES LTDA.",
                   qtde_peso2="50.000"),
    ]
    carregar_movimento(FonteFalsa({"rec": linhas}), "rec")
    dimensoes.atualizar()

    unidades = dict(
        (linha[0], linha[1])
        for linha in consultar("SELECT sigla_fonte, sigla FROM cat_unidades")
    )
    assert unidades["RMSPV"] == "RMSPIV", "a unica excecao de sigla nao foi aplicada"
    assert unidades["RMSPII"] == "RMSPII", "unidade sem excecao e identidade"

    tipos = dict(
        (linha[0], (linha[1], linha[2]))
        for linha in consultar("SELECT nome_estoque, tipo, regra FROM cat_tipos_estoque")
    )
    # as tres decisoes da Maria de 24/ago/2026, e a sentinela do que segue aberto.
    # A regra auditada e `CONG` e nao `CONGELADO`: e a palavra que de fato
    # casou -- `CONG FLV (CUCINARE)` nao contem `CONGELADO`. A coluna `regra`
    # existe para dizer o que decidiu, entao ela tem que dizer a verdade.
    assert tipos["CONG FLV (CUCINARE)"] == ("CONGELADO", "CONG")
    assert tipos["AGUA / CARVAO"] == ("SECO", "nome exato")
    assert tipos["CONSOLIDADOR"][0] == tipo_estoque.NAO_CLASSIFICADO, \
        "CONSOLIDADOR segue aberto (A-6) e tem que aparecer como sentinela"

    clientes = dict(
        (linha[0], (linha[1], linha[2]))
        for linha in consultar("SELECT raiz_cnpj, razao_social, grafias FROM cat_clientes")
    )
    assert clientes["67945071"][0] == "SAPORE S.A", \
        "a grafia de maior peso e que vira o rotulo"
    assert len(clientes["67945071"][1]) == 2, \
        "as grafias absorvidas ficam guardadas, para a tela poder declara-las"

    # recalcular nao duplica -- as tres sao upsert por chave, nao insert
    dimensoes.atualizar()
    assert _contar("cat_unidades") == 2
    assert _contar("cat_tipos_estoque") == 3
    assert _contar("cat_clientes") == 2


@tem_extracao
def test_piso_de_periodo_corta_2025_e_e_configuravel(monkeypatch):
    """O recorte da Maria (25/ago/2026): a V3 le de 2026 para frente.

    Fixado contra o arquivo de verdade porque o numero importa: sao **150**
    linhas de dez/2025 na expedicao, e o recebimento nao tem nenhuma. Se um dia
    o piso mudar sem querer, e aqui que aparece.

    O piso vive em configuracao porque a Maria nomeou o caso de uso -- comparar
    2025 com 2026 -- e a segunda metade do teste e essa promessa: baixar o piso
    devolve as linhas, sem tocar em codigo."""
    fonte = FonteCSV(DIRETORIO_DW)
    for movimento in ("rec", "exp"):
        entregues = sum(1 for _ in fonte.extrair(movimento))
        assert entregues == LINHAS[movimento], f"{movimento}: janela de 2026"
        assert NO_ARQUIVO[movimento] - entregues == FORA_DA_JANELA[movimento],             f"{movimento}: o arquivo tem mais linha do que a janela devolve"

    monkeypatch.setenv(contrato.ENV_ANO_MINIMO, "2025")
    assert sum(1 for _ in fonte.extrair("exp")) == NO_ARQUIVO["exp"],         "baixar o piso tem que devolver dez/2025 sem mexer em codigo"

    monkeypatch.setenv(contrato.ENV_ANO_MINIMO, "2027")
    assert sum(1 for _ in fonte.extrair("exp")) == 0


def test_piso_invalido_falha_antes_de_ler_qualquer_linha(monkeypatch):
    """Ano digitado errado nao pode virar "carrega tudo" nem "carrega nada"."""
    fonte = FonteCSV(DIRETORIO_DW)
    for ruim in ("26", "20226", "dois mil e vinte e seis"):
        monkeypatch.setenv(contrato.ENV_ANO_MINIMO, ruim)
        with pytest.raises(contrato.AnoMinimoInvalido, match=contrato.ENV_ANO_MINIMO):
            next(fonte.extrair("rec"))


@tem_extracao
def test_carga_completa_dos_csvs_do_dw(banco_migrado):
    """Fidelidade total contra as duas extracoes de 21/ago/2026.

    Um teste so, e grande, porque a carga das 78.768 linhas e a parte caro do
    setup -- quebrar isto em oito testes pagaria oito vezes por dado que nao
    muda. Cada assert diz o que quebrou."""
    fonte = FonteCSV(DIRETORIO_DW)
    resultados = carregar_tudo(fonte)

    # 1. tudo entrou, e nada ficou de fora do escopo
    for movimento, esperado in LINHAS.items():
        resultado = resultados[movimento]
        assert resultado.status == "ok", f"{movimento}: {resultado.erro}"
        assert resultado.linhas_carregadas == esperado, f"{movimento}: contagem"
        assert resultado.inseridas == esperado, f"{movimento}: nem tudo foi inserido"
        assert resultado.fora_escopo == 0, \
            f"{movimento}: apareceu instancia nao-SLIN, que nao existia no medido"
    assert _contar("cat_fato_recebimento") == LINHAS["rec"]
    assert _contar("cat_fato_expedicao") == LINHAS["exp"]

    # 2. a chave natural aguentou: 36.300/36.300 e 42.468/42.468 unicas. Se a
    #    fonte passar a repetir, o UNIQUE derruba a carga em vez de duplicar.
    for tabela, esperado in (
        ("cat_fato_recebimento", LINHAS["rec"]),
        ("cat_fato_expedicao", LINHAS["exp"]),
    ):
        distintas = consultar(
            f"SELECT count(*) FROM (SELECT DISTINCT "
            f"{', '.join(contrato.CHAVE_NATURAL)} FROM {tabela}) t"
        )[0][0]
        assert distintas == esperado, f"{tabela}: chave natural repetiu"

    # 3. a guia cancelada continua com medida NULL, nao zero -- e a limitacao
    #    que a tela tem que declarar, e zero a apagaria
    cancelada = consultar(
        """
        SELECT qtde_vol2, qtde_peso2, qtde_pbrt2, qtde_vlr
        FROM cat_fato_recebimento
        WHERE num_gem = %s AND status_processo = 'Cancelado'
        """,
        (GUIA_CANCELADA,),
    )
    assert len(cancelada) == 1, "a guia cancelada medida em 21/ago sumiu"
    assert cancelada[0] == (None, None, None, None), \
        "medida vazia virou zero -- 'cancelada' deixou de ser distinguivel de 'pesou zero'"

    # 4. zero a esquerda sobreviveu ao banco
    assert consultar(
        "SELECT count(*) FROM cat_fato_recebimento WHERE num_gem LIKE '0%%'"
    )[0][0] > 0, "nenhum num_gem com zero a esquerda: o identificador virou numero"

    # 5. as dimensoes, no tamanho medido
    assert _contar("cat_unidades") == UNIDADES
    assert _contar("cat_tipos_estoque") == NOMES_ESTOQUE
    assert _contar("cat_clientes") == RAIZES_CLIENTE
    assert consultar(
        "SELECT sigla FROM cat_unidades WHERE sigla_fonte = 'RMSPV'"
    ) == [("RMSPIV",)]
    varias = consultar(
        "SELECT count(*) FROM cat_clientes WHERE jsonb_array_length(grafias) > 1"
    )[0][0]
    assert varias == RAIZES_COM_VARIAS_GRAFIAS, \
        "o numero de raizes com mais de uma grafia mudou desde a medicao"

    # 6. idempotencia sobre o dado de verdade: a segunda rodada e inocua
    donos_antes = consultar(
        "SELECT carga_id, count(*) FROM cat_fato_recebimento GROUP BY 1 ORDER BY 1"
    )
    de_novo = carregar_tudo(fonte)
    for movimento, esperado in LINHAS.items():
        segunda = de_novo[movimento]
        assert (segunda.inseridas, segunda.atualizadas) == (0, 0), \
            f"{movimento}: a segunda rodada mexeu no banco"
        assert segunda.iguais == esperado
    assert _contar("cat_fato_recebimento") == LINHAS["rec"]
    assert _contar("cat_fato_expedicao") == LINHAS["exp"]
    assert consultar(
        "SELECT carga_id, count(*) FROM cat_fato_recebimento GROUP BY 1 ORDER BY 1"
    ) == donos_antes, "carga_id mudou sem o conteudo ter mudado"

    # 7. incremental a partir da marca d'agua: nada mudou na fonte -> sem_dado
    for movimento in ("rec", "exp"):
        vazia = carregar_movimento(
            fonte, movimento, desde=destino.marca_dagua(movimento)
        )
        assert vazia.status == "sem_dado", \
            f"{movimento}: o incremental releu linha que ja estava carregada"


def test_carregador_nao_usa_o_pool_do_app():
    """O carregador abre conexao propria, sem o `statement_timeout` de 30s do
    app web: interromper carga em lote no meio nao protege ninguem, so
    transforma rodada lenta em rodada perdida."""
    assert "DATABASE_URL" in os.environ
    conn = destino.conexao()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW statement_timeout")
            assert cur.fetchone()[0] == "0", \
                "a conexao do carregador nao deve herdar limite de statement"
    finally:
        conn.close()


# ------------------------------------------- o que o CLI diz quando falta algo
# Duas vezes na mesma sessao, no fechamento do V3.5 (26/ago/2026), a carga morreu
# com `carga falhou: 'DATABASE_URL'` -- um `KeyError` cru vazando pelo tratamento
# generico. A mensagem nao mentia, so nao ajudava: nao dizia que variavel de
# ambiente vale por terminal, nem que o `.env` da raiz e lido pelo
# docker-compose e nao pelo Python.
#
# O CLI de usuarios (V3.4) ja tinha resolvido isto. O carregador nao herdou --
# e e por isso que o texto agora mora em `catering/ambiente.py`, importado pelos
# dois.
def _rodar_cli(argv):
    """Chama o CLI e devolve o texto do `SystemExit`, ou None se nao saiu."""
    from catering.carga.__main__ import main

    try:
        main(argv)
    except SystemExit as saida:
        return str(saida.code)
    return None


def test_sem_database_url_o_cli_diz_o_que_fazer(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    texto = _rodar_cli(["--de", "docs/Analise"])
    assert texto and "DATABASE_URL" in texto
    assert "vale por terminal" in texto, \
        "a mensagem tem que explicar a armadilha, nao so nomear a variavel"
    assert "docker-compose" in texto, "e que o .env nao e lido pelo Python"
    assert "KeyError" not in texto


def test_sondar_nao_exige_database_url(monkeypatch):
    """`--sondar` nao toca no Postgres -- exigir a variavel ali seria pedagio
    por nada, e ele e justamente o primeiro comando numa maquina onde o banco
    local ainda nao existe."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DW_USER", "nao-conecta")
    monkeypatch.setenv("DW_SENHA", "nao-conecta")
    texto = _rodar_cli(["--fonte", "oracle", "--sondar", "--movimento", "rec"])
    assert not (texto and "DATABASE_URL" in texto), \
        "--sondar cobrou DATABASE_URL, que ele nao usa"


def test_sem_credencial_do_dw_o_cli_nomeia_as_duas(monkeypatch):
    """Antes de abrir conexao e antes de registrar rodada: a falta e conhecida
    na entrada, e recusar ali evita uma linha em `cat_cargas` com
    `status='erro'` por um motivo que se poderia saber antes de comecar."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.delenv("DW_USER", raising=False)
    monkeypatch.delenv("DW_SENHA", raising=False)
    texto = _rodar_cli(["--fonte", "oracle"])
    assert texto and "DW_USER" in texto and "DW_SENHA" in texto, \
        "nomear so uma manda conferir o lugar errado"
    assert "argumento de linha de comando" in texto, \
        "a mensagem tem que dizer para NAO passar senha como argumento"


def test_a_orientacao_de_ambiente_nao_carrega_valor_de_credencial(monkeypatch):
    """A mensagem e impressa no terminal e colada em chat e em ticket. Ela pode
    dizer o NOME da variavel; nunca o valor."""
    SEGREDOS = ("usuario-secreto-de-teste", "senha-secreta-de-teste")

    # ramo 1: falta o banco, e as credenciais do DW ESTAO no ambiente -- o caso
    # em que teria como vazar, porque o valor existe
    monkeypatch.setenv("DW_USER", SEGREDOS[0])
    monkeypatch.setenv("DW_SENHA", SEGREDOS[1])
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sem_banco = _rodar_cli(["--de", "docs/Analise"]) or ""
    assert "DATABASE_URL" in sem_banco, "nao caiu no ramo esperado"

    # ramo 2: falta a credencial do DW
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.delenv("DW_USER")
    monkeypatch.setenv("DW_SENHA", SEGREDOS[1])
    sem_dw = _rodar_cli(["--fonte", "oracle"]) or ""
    assert "DW_USER" in sem_dw, "nao caiu no ramo esperado"

    for texto in (sem_banco, sem_dw):
        for segredo in SEGREDOS:
            assert segredo not in texto, \
                "valor de credencial dentro de mensagem de erro"
