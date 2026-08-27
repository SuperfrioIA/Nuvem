"""V3.2 -- o app da V3: endpoints e o encaixe HTTP.

A regra de negocio da Matriz esta coberta em `test_catering_matriz.py`, contra o
servico direto. Aqui so o que e proprio do HTTP: contrato da resposta, recusa de
filtro invalido com 400 (e nao 500), precisao do numero no JSON, e a
independencia do app da V2.

## App proprio, e este teste guarda isso

Decisao da Maria em 24/ago/2026: a V3 e um projeto separado, e a V2 esta
congelada. `test_app_da_v3_nao_depende_do_app_da_v2` existe para que "separado"
nao vire promessa: se alguem importar um router do `backend/` aqui, o teste
quebra. Sem ele, a separacao dura ate o primeiro atalho conveniente.

## Com login, a partir do V3.4

A `cliente_v3` entra **logada como admin**. A exigencia de sessao em si (401 sem
cookie, 403 de visualizador no que e de admin, cookie forjado recusado) vive em
`test_catering_seguranca.py` -- separada de proposito: se a autenticacao quebrar,
o sinal tem que aparecer como falha de seguranca, e nao como catorze falhas de
Matriz apontando para o lugar errado.
"""

import re
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from catering import contrato
from catering.app import app
from catering.consulta import download
from catering.seguranca import identidade, usuarios
from tests.conftest import consultar
from tests.test_catering_matriz import _semear_entrada, _semear_saida


SENHA_DE_TESTE = "senha-de-teste-v3"


@pytest.fixture
def cliente_v3(banco_migrado):
    """Cliente **autenticado** como admin.

    A partir do V3.4 todo endpoint de dado exige sessao. Estes testes cuidam do
    encaixe HTTP da consulta, nao do login -- entao entram logados, e a prova de
    que o app **recusa** quem nao esta logada mora em
    `test_catering_seguranca.py`. Se a exigencia de sessao fosse verificada aqui,
    cada teste de consulta passaria a depender do login e uma quebra de
    autenticacao apareceria como 14 falhas de Matriz."""
    identidade.zerar_freio()
    usuarios.criar("teste.admin", "Admin de teste", "admin", SENHA_DE_TESTE)
    with TestClient(app) as c:
        entrada = c.post(
            "/login", data={"login": "teste.admin", "senha": SENHA_DE_TESTE}
        )
        assert entrada.status_code == 200, entrada.text
        yield c


def semear(cursor, semeador, **kwargs):
    """Semeia e **comita na hora**.

    O app le por OUTRA conexao, atras do `TestClient` -- sem commit explicito a
    insercao nao seria vista, e a falha apareceria como "a Matriz voltou vazia",
    longe da causa. A mesma armadilha esta documentada no
    `tests/test_volumetria_router.py` da V2."""
    semeador(cursor, **kwargs)
    cursor.connection.commit()


def test_health_responde_com_o_estado_do_banco(cliente_v3):
    """O compose do V3.6 vai depender deste endpoint."""
    resposta = cliente_v3.get("/health")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] is True
    assert corpo["banco"] == "ok"


def test_opcoes_saem_do_dado_e_nao_de_lista_fixa(cliente_v3, cursor):
    """Unidade, cliente e operacao novos tem que aparecer no filtro sozinhos.
    Lista fixa aqui seria a mesma armadilha do de-para da V2: a fonte anda e a
    tela nao."""
    semear(cursor, _semear_entrada, sigla="RMSPII", cliente="67945071")
    semear(cursor, _semear_entrada, sigla="XPTO", cliente="99999999",
           gem="0000000002", operacao="OPERACAO NOVA")

    corpo = cliente_v3.get("/api/opcoes").json()
    assert "XPTO" in corpo["unidades"], "unidade nova nao apareceu no filtro"
    assert "99999999" in [c["chave"] for c in corpo["clientes"]]
    assert "OPERACAO NOVA" in corpo["operacoes"]["rec"]
    # O periodo agora sai em DIA, e deixou de ser o padrao da tela: virou a dica
    # de alcance ("o dado disponivel vai de X a Y"), para quem nao sabe que
    # 2023 esta no banco poder filtrar para tras.
    assert corpo["periodo"]["de"] == "2026-01-05"

    # A abertura e outra coisa: e onde a tela COMECA. Janeiro do ano corrente
    # ate hoje, e nunca antes do primeiro dia que tem dado.
    hoje = date.today()
    assert corpo["abertura"]["ate"] == hoje.isoformat()
    assert corpo["abertura"]["de"] >= f"{hoje.year:04d}-01-01"
    assert corpo["abertura"]["de"] <= corpo["abertura"]["ate"], \
        "a tela abriria com periodo invertido"

    # os dois tetos do download vem do Python, e nao de uma copia no JavaScript
    assert corpo["teto_confirmacao"] == download.TETO_CONFIRMACAO
    assert corpo["teto_xlsx"] == download.TETO_XLSX

    # as lentes vem do contrato, com o pallet marcado como so-entrada para a
    # tela poder desabilitar em vez de esconder
    lentes = {l["chave"]: l for l in corpo["lentes"]}
    assert set(lentes) == set(contrato.LENTES)
    assert lentes["pal"]["so_entrada"] is True
    assert lentes["liq"]["so_entrada"] is False
    assert lentes["liq"]["nome"] == "Peso líquido", \
        "rotulo de tela tem que vir acentuado"

    # procedencia: de quando e o dado que a tela mostra
    assert corpo["cargas"], "a tela precisa poder dizer de quando o dado e"


def test_matriz_devolve_a_arvore_e_o_recorte_aplicado(cliente_v3, cursor):
    semear(cursor, _semear_entrada, peso="12.500")
    resposta = cliente_v3.get(
        "/api/matriz",
        params={"de": "2026-01-01", "ate": "2026-01-31", "movimento": "rec",
                "lente": "liq"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["meses"] == ["2026-01"]
    assert corpo["niveis"] == ["unidade", "cliente", "operacao"]
    assert corpo["lente"] == {"chave": "liq", "nome": "Peso líquido", "unidade": "t"}
    # o recorte volta ecoado: a tela nunca deve adivinhar o que pediu, e o
    # download do V3.3 precisa registrar isto na auditoria
    assert corpo["filtros"]["de"] == "2026-01-01"
    assert corpo["filtros"]["ate"] == "2026-01-31"
    assert corpo["filtros"]["movimento"] == "rec"
    assert corpo["filtros"]["dias"] == [], "sem filtro de dia, o eco e vazio"

    unidade = corpo["linhas"][0]
    assert unidade["chave"] == "RMSPII"
    assert unidade["filhos"][0]["filhos"][0]["nivel"] == "operacao"


def test_numero_vai_como_texto_para_nao_perder_precisao(cliente_v3, cursor):
    """Peso e valor em R$ nao devem passar pelo float do JavaScript. Decimal sai
    como string, e a tela formata."""
    semear(cursor, _semear_entrada, peso="12345.678")
    corpo = cliente_v3.get(
        "/api/matriz",
        params={"de": "2026-01-01", "ate": "2026-01-31", "lente": "liq"},
    ).json()
    valor = corpo["total"]["2026-01"]
    assert isinstance(valor, str), f"veio {type(valor).__name__}, esperado string"
    assert Decimal(valor) == Decimal("12345.678")


def test_filtro_invalido_e_400_e_nao_500(cliente_v3):
    """500 aqui esconderia erro do chamador atras de erro do servidor -- e
    manda quem esta depurando olhar o lugar errado."""
    for params, pedaco in (
        ({"de": "2026-01-01", "ate": "2026-01-31", "lente": "xpto"}, "lente"),
        ({"de": "2026-01-01", "ate": "2026-01-31", "movimento": "xpto"}, "movimento"),
        ({"de": "2026-01-01", "ate": "2026-01-31", "faixa": "xpto"}, "faixa"),
        ({"de": "janeiro", "ate": "2026-01-31"}, "AAAA-MM-DD"),
        ({"de": "2026-01", "ate": "2026-01"}, "AAAA-MM-DD"),
        ({"de": "2026-01-01", "ate": "2026-01-31", "dia": "32"}, "dia"),
        ({"de": "2026-01-01", "ate": "2026-01-31", "dia": "x"}, "dia"),
        ({"de": "2026-03-01", "ate": "2026-01-31"}, "invertido"),
    ):
        resposta = cliente_v3.get("/api/matriz", params=params)
        assert resposta.status_code == 400, f"{params} devolveu {resposta.status_code}"
        assert pedaco in resposta.json()["detail"]

    # `de` e `ate` sao obrigatorios: recorte implicito seria a tela mostrando um
    # periodo que ninguem pediu
    assert cliente_v3.get("/api/matriz").status_code == 422


def test_saida_traz_as_tres_faixas_e_o_aviso(cliente_v3, cursor):
    semear(cursor, _semear_saida)
    corpo = cliente_v3.get(
        "/api/matriz",
        params={"de": "2026-01-01", "ate": "2026-01-31", "movimento": "exp",
                "lente": "liq", "faixa": "solicitado"},
    ).json()

    assert corpo["niveis"] == ["unidade", "cliente", "faixa", "operacao"]
    cliente = corpo["linhas"][0]["filhos"][0]
    assert [f["chave"] for f in cliente["filhos"]] == list(contrato.FAIXAS)
    assert any("não somam entre si" in a for a in corpo["avisos"])


def test_pallet_na_saida_devolve_vazio_com_aviso(cliente_v3, cursor):
    semear(cursor, _semear_saida)
    corpo = cliente_v3.get(
        "/api/matriz",
        params={"de": "2026-01-01", "ate": "2026-01-31", "movimento": "exp",
                "lente": "pal"},
    ).json()
    assert corpo["linhas"] == []
    assert corpo["total"]["2026-01"] is None
    assert any("só existe na entrada" in a for a in corpo["avisos"])


def test_pagina_e_o_logo_sao_servidos(cliente_v3):
    """O logo da marca e obrigatorio na tela, e e servido como arquivo -- o PNG
    tem 147 KB e inline entraria em toda resposta da pagina."""
    pagina = cliente_v3.get("/")
    assert pagina.status_code == 200
    assert "Volumetria de catering" in pagina.text
    assert 'src="/logo.png"' in pagina.text

    logo = cliente_v3.get("/logo.png")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/png"


def test_todo_filtro_de_multipla_escolha_tem_painel_de_caixas(cliente_v3):
    """V3.7.1 -- os cinco `<select multiple>` e a lista `COM_CAIXAS` tem que ser
    o MESMO conjunto.

    O painel de caixas de selecao e uma camada sobre o select, que continua no
    DOM como fonte da verdade. Quem entrar depois e acrescentar um sexto filtro
    de multipla escolha sem por ele em `COM_CAIXAS` produz um defeito silencioso
    e feio: o select fica visivel entre botoes (a barra volta a ter duas
    alturas), o `Limpar` deixa de zerar aquele filtro -- porque o Limpar tambem
    itera `COM_CAIXAS` -- e o recorte sai com um filtro em pe que a tela nao
    mostra. Nada disso levanta erro; so sai numero de menos.

    Este teste e estrutural de proposito: le o HTML servido, nao executa JS. O
    projeto nao tem suite de JavaScript, e o comportamento do painel (marcar,
    "Selecionar tudo", Esc, clique fora) se prova no navegador."""
    pagina = cliente_v3.get("/")
    assert pagina.status_code == 200
    html = pagina.text

    ids_no_html = set(re.findall(r'<select id="([^"]+)" multiple', html))

    declarada = re.search(r"const COM_CAIXAS = \[([^\]]+)\];", html)
    assert declarada, "COM_CAIXAS desapareceu do script da tela"
    ids_com_painel = {
        alvo.strip().strip("'\"").lstrip("#")
        for alvo in declarada.group(1).split(",")
    }

    assert ids_no_html == ids_com_painel, (
        "filtro de multipla escolha sem painel de caixas (ou o contrario): "
        f"no HTML {sorted(ids_no_html)}, em COM_CAIXAS {sorted(ids_com_painel)}"
    )
    # A lista de hoje, escrita para o teste falar do numero e nao so da relacao:
    # unidade, cliente, tipo de estoque, operacao e dia do mes.
    assert len(ids_no_html) == 5


def test_app_da_v3_nao_depende_do_app_da_v2():
    """A separacao tem que ser verificavel, nao prometida: a V2 esta congelada e
    a V3 nao importa codigo dela. Se alguem pendurar um router do `backend/`
    aqui por conveniencia, este teste quebra."""
    import ast
    import inspect

    import catering.app as modulo

    arvore = ast.parse(inspect.getsource(modulo))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
    # Confere os IMPORTS, nao o texto: a docstring do modulo cita
    # `backend/main.py` de proposito, para explicar por que ele NAO e usado.
    do_backend = sorted(m for m in importados if m.split(".")[0] == "backend")
    assert not do_backend, \
        f"o app da V3 passou a importar da V2 congelada: {do_backend}"

    caminhos = {rota.path for rota in app.routes}
    assert {"/", "/health", "/api/matriz", "/api/opcoes", "/logo.png"} <= caminhos
    # nenhuma rota da V2 foi arrastada para dentro deste app
    for rota_v2 in ("/admin", "/cockpit", "/nuvem", "/laboratorio", "/linhagem"):
        assert rota_v2 not in caminhos, f"{rota_v2} nao pertence ao app da V3"


# ====================================================== V3.3: planilha
def test_planilha_pela_api(cliente_v3, cursor):
    semear(cursor, _semear_entrada, peso="12.500")
    corpo = cliente_v3.get(
        "/api/planilha",
        params={"de": "2026-01-01", "ate": "2026-01-31", "movimento": "rec", "lente": "liq"},
    ).json()

    assert [c["chave"] for c in corpo["colunas"]] == [
        "dia", "unidade", "cliente", "guia", "operacao", "tipo_estoque", "valor"
    ]
    assert corpo["paginacao"]["por_pagina"] == 100
    assert corpo["paginacao"]["total_linhas"] == 1
    linha = corpo["linhas"][0]
    assert linha["guia"] == "0000000001"
    assert linha["valor"] == "12.500", "medida vai como texto, para nao perder precisao"
    # o recorte volta ecoado, como na Matriz
    assert corpo["filtros"]["de"] == "2026-01-01"


# ------------------------------------------------- abertura da tela e dia do mes
def test_abertura_da_tela_e_janeiro_do_ano_corrente(monkeypatch):
    """O padrao e rolante: janeiro do ANO de hoje.

    Testado com `hoje` injetado, e nao com o relogio: funcao que le o relogio
    por dentro so se testa congelando o tempo, e o proximo 1o de janeiro nao e
    hora de descobrir isso."""
    monkeypatch.delenv(contrato.ENV_ABERTURA_DE, raising=False)
    assert contrato.abertura_de(date(2026, 8, 26)) == date(2026, 1, 1)
    assert contrato.abertura_de(date(2027, 1, 1)) == date(2027, 1, 1)
    assert contrato.abertura_de(date(2030, 12, 31)) == date(2030, 1, 1)

    # o valor explicito vale o mesmo que a ausencia
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, contrato.ABERTURA_ANO_CORRENTE)
    assert contrato.abertura_de(date(2026, 8, 26)) == date(2026, 1, 1)

    # pinar e escrever a data -- e o que resolve o janeiro de 2027 com uma
    # coluna so, sem commit
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, "2026-01-01")
    assert contrato.abertura_de(date(2027, 3, 15)) == date(2026, 1, 1)


@pytest.mark.parametrize("ruim", ["janeiro", "2026-01", "20260101", "2026-02-30", "0"])
def test_abertura_invalida_falha_nomeando_a_variavel(monkeypatch, ruim):
    """Valor escrito errado tem que apontar para a configuracao, e nao virar
    "abre em 1970" em silencio."""
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, ruim)
    with pytest.raises(contrato.AberturaInvalida, match=contrato.ENV_ABERTURA_DE):
        contrato.abertura_de(date(2026, 8, 26))


def test_abertura_pinada_chega_na_tela(cliente_v3, cursor, monkeypatch):
    """A configuracao tem que atravessar o endpoint, e nao so a funcao."""
    semear(cursor, _semear_entrada)
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, "2026-01-20")
    corpo = cliente_v3.get("/api/opcoes").json()
    assert corpo["abertura"]["de"] == "2026-01-20"

    # Data pinada ANTES do primeiro dia com dado vale como pedida: a alternativa
    # (travar no primeiro dia do dado) foi construida, medida no navegador e
    # DESFEITA -- ela fazia o cabecalho declarar `2026-01 (02-31)` num janeiro
    # inteiro, so porque o dado comeca no dia 02. Marca de mes parcial que nasce
    # ligada no padrao e marca que ninguem mais le. Coluna vazia a esquerda nao
    # custa nada; marcador que mente, custa.
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, "2020-05-04")
    corpo = cliente_v3.get("/api/opcoes").json()
    assert corpo["abertura"]["de"] == "2020-05-04"
    assert corpo["periodo"]["de"] == "2026-01-05",         "o alcance do dado continua sendo dica, e nao trava da abertura"


def test_abertura_pinada_no_futuro_nao_abre_com_periodo_invertido(cliente_v3, monkeypatch):
    """`de > ate` derrubaria a tela com 400 na cara de quem entrou -- e por um
    valor de configuracao que a pessoa nem sabe que existe."""
    monkeypatch.setenv(contrato.ENV_ABERTURA_DE, "2099-12-31")
    corpo = cliente_v3.get("/api/opcoes").json()
    assert corpo["abertura"]["de"] == corpo["abertura"]["ate"]


def test_filtro_de_dia_do_mes_recorta_pela_api(cliente_v3, cursor):
    """O `dia` chega como texto na URL e tem que recortar de verdade.

    Filtro que nao filtra e pior que filtro ausente: a tela afirma um recorte
    que o numero nao respeita."""
    semear(cursor, _semear_entrada, calendario="2026-01-05", peso="10.000")
    semear(cursor, _semear_entrada, calendario="2026-01-06", peso="20.000",
           gem="0000000002")
    semear(cursor, _semear_entrada, calendario="2026-02-05", peso="30.000",
           gem="0000000003")

    def total(**extra):
        corpo = cliente_v3.get("/api/matriz", params={
            "de": "2026-01-01", "ate": "2026-02-28", **extra
        }).json()
        return corpo, sum(Decimal(v) for v in corpo["total"].values() if v)

    corpo, tudo = total()
    assert tudo == Decimal("60.000")
    assert corpo["avisos"] == [] or all("dia do mês" not in a for a in corpo["avisos"])

    # dia 05 dos DOIS meses -- e isto que distingue o filtro de dia do periodo
    corpo, so_dia_5 = total(dia="5")
    assert so_dia_5 == Decimal("40.000"), "o dia do mes tem que valer em todo mês"
    assert corpo["filtros"]["dias"] == [5]
    assert any("dia do mês" in a for a in corpo["avisos"]), \
        "coluna que deixou de ser o mes inteiro sem aviso na tela"

    _, dois_dias = total(dia=["5", "6"])
    assert dois_dias == Decimal("60.000")
    _, nenhum = total(dia="28")
    assert nenhum == 0


def test_planilha_e_matriz_usam_o_mesmo_recorte(cliente_v3, cursor):
    """Se a planilha e a Matriz discordassem sobre quais linhas estao no
    recorte, a tela mostraria um numero e baixaria outro."""
    semear(cursor, _semear_entrada, sigla="RMSPII", peso="10.000")
    semear(cursor, _semear_entrada, sigla="CWBIII", gem="0000000002", peso="20.000")

    params = {"de": "2026-01-01", "ate": "2026-01-31", "movimento": "rec",
              "lente": "liq", "unidade": ["RMSPII"]}
    da_matriz = cliente_v3.get("/api/matriz", params=params).json()
    da_planilha = cliente_v3.get("/api/planilha", params=params).json()

    assert da_matriz["total"]["2026-01"] == "10.000"
    assert da_planilha["paginacao"]["total_linhas"] == 1
    assert da_planilha["linhas"][0]["valor"] == "10.000"


# ====================================================== V3.3: download
def test_download_csv_pela_api(cliente_v3, cursor):
    semear(cursor, _semear_entrada, peso="1234.567")
    resposta = cliente_v3.get(
        "/api/download",
        params={"de": "2026-01-01", "ate": "2026-01-31", "movimento": "rec",
                "formato": "csv"},
    )
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert "catering_entrada_2026-01-01_a_2026-01-31.csv" in \
        resposta.headers["content-disposition"]

    texto = resposta.content.decode("utf-8-sig")
    assert resposta.content.startswith(b"\xef\xbb\xbf"), "faltou o BOM"
    linhas = texto.strip().splitlines()
    assert len(linhas) == 2
    assert "1234,567" in linhas[1], "decimal deveria sair com virgula"

    # e ficou auditado, com o recorte
    registro = consultar(
        "SELECT formato, linhas, status, recorte->>'movimento'"
        " FROM cat_auditoria ORDER BY id DESC LIMIT 1"
    )[0]
    assert registro == ("csv", 1, "ok", "rec")


def test_download_xlsx_pela_api(cliente_v3, cursor):
    semear(cursor, _semear_entrada, gem="0000000609")
    resposta = cliente_v3.get(
        "/api/download",
        params={"de": "2026-01-01", "ate": "2026-01-31", "formato": "xlsx"},
    )
    assert resposta.status_code == 200
    assert "spreadsheetml" in resposta.headers["content-type"]
    assert resposta.content[:2] == b"PK", "xlsx e um zip"


def test_download_ignora_pagina_e_recusa_formato_desconhecido(cliente_v3, cursor):
    """O download e SEMPRE o recorte inteiro (contrato) -- `pagina` nao entra:
    baixar uma pagina so nao e baixar o recorte."""
    for i in range(1, 4):
        semear(cursor, _semear_entrada, gem=f"{i:010d}")

    resposta = cliente_v3.get(
        "/api/download",
        params={"de": "2026-01-01", "ate": "2026-01-31", "formato": "csv", "pagina": 2},
    )
    linhas = resposta.content.decode("utf-8-sig").strip().splitlines()
    assert len(linhas) == 4, "o download deveria trazer as 3 linhas, nao uma pagina"

    ruim = cliente_v3.get(
        "/api/download",
        params={"de": "2026-01-01", "ate": "2026-01-31", "formato": "pdf"},
    )
    assert ruim.status_code == 400
    assert "formato" in ruim.json()["detail"]


# ---------------------------------------------------------- fuso de exibicao
# O dado sempre esteve certo: `terminada_em` e `criado_em` sao `timestamptz` e
# guardam UTC. O defeito era na LEITURA -- o `to_char` renderiza no fuso da
# sessao do Postgres, `Etc/UTC` no container, e uma carga das 09h45 aparecia
# como 12h45. Medido no fechamento do V3.5, em 26/ago/2026.
#
# Estes testes gravam um instante UTC **conhecido** e conferem o texto que o
# endpoint devolve. Sem valor fixo eles passariam por acidente em qualquer
# maquina cujo Postgres ja estivesse no fuso certo -- e falhariam na VM.
INSTANTE_UTC = "2026-08-26 12:45:33+00"
EM_SAO_PAULO = "26/08/2026 09:45"      # UTC-3
EM_MANAUS = "26/08/2026 08:45"         # UTC-4, para provar que e configuravel


def test_o_rodape_diz_a_hora_no_fuso_de_exibicao_e_nao_em_utc(cliente_v3, cursor):
    """Rodape com hora no futuro destroi a confianca no proprio rodape: ele
    existe para dizer de quando o dado e."""
    semear(cursor, _semear_entrada)
    cursor.execute("UPDATE cat_cargas SET terminada_em = %s", (INSTANTE_UTC,))
    cursor.connection.commit()

    cargas = cliente_v3.get("/api/opcoes").json()["cargas"]
    assert cargas, "sem carga nao ha o que conferir"
    assert cargas[0]["quando"] == EM_SAO_PAULO, (
        f"a tela mostrou {cargas[0]['quando']!r} para um instante que e "
        f"{EM_SAO_PAULO} em Sao Paulo -- provavelmente esta exibindo UTC cru"
    )


def test_a_auditoria_diz_a_hora_no_fuso_de_exibicao(cliente_v3, cursor):
    """Este e o que pesa mais que o rodape: hora errada em registro de auditoria
    e problema de rastreabilidade. E o que se consulta quando alguem pergunta
    quem baixou o que, e quando."""
    # o proprio login do `cliente_v3` ja gerou o registro
    cursor.execute("UPDATE cat_auditoria SET criado_em = %s", (INSTANTE_UTC,))
    cursor.connection.commit()

    linhas = cliente_v3.get("/api/auditoria").json()
    assert linhas, "o login da fixture devia ter deixado rastro"
    assert linhas[0]["quando"].startswith(EM_SAO_PAULO), (
        f"a auditoria mostrou {linhas[0]['quando']!r}, e nao {EM_SAO_PAULO}"
    )


def test_o_fuso_de_exibicao_vem_da_configuracao(cliente_v3, cursor, monkeypatch):
    """Configuracao e nao constante enterrada: o dia em que a exibicao passar a
    ser no fuso de quem le, tem que haver **um** lugar para mexer."""
    semear(cursor, _semear_entrada)
    cursor.execute("UPDATE cat_cargas SET terminada_em = %s", (INSTANTE_UTC,))
    cursor.connection.commit()

    monkeypatch.setenv(contrato.ENV_FUSO_EXIBICAO, "America/Manaus")
    cargas = cliente_v3.get("/api/opcoes").json()["cargas"]
    assert cargas[0]["quando"] == EM_MANAUS, (
        "trocar CAT_FUSO_EXIBICAO nao mudou o que a tela mostra"
    )


def test_fuso_invalido_falha_nomeando_a_variavel(monkeypatch):
    """Na LEITURA, nao no uso. A alternativa e o Postgres estourar no meio de
    uma consulta de tela, com uma mensagem que nao aponta para a configuracao.

    `America/SaoPaulo` (sem o `_`) e o erro que de fato se comete."""
    monkeypatch.setenv(contrato.ENV_FUSO_EXIBICAO, "America/SaoPaulo")
    with pytest.raises(contrato.FusoInvalido) as erro:
        contrato.fuso_exibicao()
    assert contrato.ENV_FUSO_EXIBICAO in str(erro.value), \
        "a mensagem tem que nomear a variavel, senao nao ajuda"

    monkeypatch.delenv(contrato.ENV_FUSO_EXIBICAO)
    assert contrato.fuso_exibicao() == contrato.FUSO_EXIBICAO_PADRAO


def test_o_fuso_entra_por_bind_e_nao_por_concatenacao():
    """Nome de fuso vem de variavel de ambiente, e variavel de ambiente
    concatenada em SQL e injecao esperando a vez -- mesmo local, mesmo validada
    antes. A guarda e estatica porque o caminho de ataque nao aparece em teste
    de comportamento: ele aparece na forma como o statement foi montado."""
    import ast
    import pathlib

    fonte = pathlib.Path("catering/app.py").read_text(encoding="utf-8")
    assert "AT TIME ZONE %s" in fonte, "o fuso deixou de entrar por bind"
    for proibido in ('AT TIME ZONE \'" +', "AT TIME ZONE '{", 'f"AT TIME ZONE'):
        assert proibido not in fonte, f"fuso interpolado em SQL: {proibido!r}"

    # e nenhum literal do modulo carrega o nome do fuso: ele vem do contrato
    arvore = ast.parse(fonte)
    literais = [n.value for n in ast.walk(arvore)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [l for l in literais if "America/" in l], \
        "nome de fuso escrito no app -- ele pertence a contrato.fuso_exibicao()"


def test_conjunta_e_visao_de_matriz_e_a_planilha_e_o_download_recusam_com_400(
        cliente_v3, cursor):
    """V3.7.2 -- "Entrada + saida" existe na Matriz e NAO existe na linha crua.

    A Matriz agrega, e por isso pode somar os dois movimentos. A planilha mostra
    linha crua e o download leva a linha inteira -- e as duas tabelas do DW tem
    36 e 46 colunas, com contratos proprios. Nao existe "linha crua entrada +
    saida", entao os dois recusam.

    **400 e nao 500**, e a mensagem diz o que fazer: e pedido que nao existe, e
    nao servidor quebrado. Sem esta recusa o pedido chegaria em
    `recorte.de_para_where`, que levanta -- e viraria erro de servidor.

    E o download recusa ANTES de abrir a auditoria: registro de download que nao
    saiu e ruido numa trilha usada para responder quem baixou o que."""
    semear(cursor, _semear_entrada, peso="140.000")
    semear(cursor, _semear_saida)
    base = {"de": "2026-01-01", "ate": "2026-01-31", "movimento": "amb"}

    da_matriz = cliente_v3.get("/api/matriz", params=base)
    assert da_matriz.status_code == 200
    corpo = da_matriz.json()
    assert corpo["niveis"] == ["unidade", "cliente", "movimento"]
    assert Decimal(corpo["total"]["2026-01"]) == Decimal("240.000"), \
        "140 da entrada + 100 do solicitado da saida"

    recusas = (
        ("A planilha", cliente_v3.get("/api/planilha", params=base)),
        ("O download csv", cliente_v3.get(
            "/api/download", params={**base, "formato": "csv"})),
        ("O download xlsx", cliente_v3.get(
            "/api/download", params={**base, "formato": "xlsx"})),
    )
    for quem, resposta in recusas:
        assert resposta.status_code == 400, \
            f"{quem} devolveu {resposta.status_code}, e nao 400"
        assert "um movimento por vez" in resposta.json()["detail"], \
            f"{quem} recusou sem dizer o que fazer"

    assert consultar(
        "SELECT count(*) FROM cat_auditoria WHERE evento = 'download'"
    )[0][0] == 0, "download recusado nao pode virar registro de download"


def test_as_opcoes_dizem_os_tres_movimentos_da_tela(cliente_v3):
    """O rotulo e a regra "so na Matriz" vem do Python, e nao de uma copia no
    JavaScript. Com duas copias, acrescentar um movimento (estoque e transporte
    existem no DW, ver A-8) exigiria lembrar de dois lugares."""
    opcoes = cliente_v3.get("/api/opcoes").json()
    movimentos = {m["chave"]: m for m in opcoes["movimentos"]}
    assert list(movimentos) == ["rec", "exp", "amb"]
    assert movimentos["amb"]["rotulo"] == "Entrada + saída"
    assert movimentos["amb"]["so_matriz"] is True
    assert not movimentos["rec"]["so_matriz"]
    assert not movimentos["exp"]["so_matriz"]
