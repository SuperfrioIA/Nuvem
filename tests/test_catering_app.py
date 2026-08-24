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

## Sem login neste lote

Login e o V3.4 e o deploy e o V3.6, nesta ordem de proposito -- nada sem
autenticacao chega a VM. Estes testes batem no app sem credencial porque e assim
que ele existe hoje; quando o V3.4 entrar, e aqui que a exigencia de sessao vai
ser fixada.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from catering import contrato
from catering.app import app
from tests.conftest import consultar
from tests.test_catering_matriz import _semear_entrada, _semear_saida


@pytest.fixture
def cliente_v3(banco_migrado):
    with TestClient(app) as c:
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
    assert corpo["periodo"]["de"] == "2026-01"

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
        params={"de": "2026-01", "ate": "2026-01", "movimento": "rec",
                "lente": "liq"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["meses"] == ["2026-01"]
    assert corpo["niveis"] == ["unidade", "cliente", "operacao"]
    assert corpo["lente"] == {"chave": "liq", "nome": "Peso líquido", "unidade": "t"}
    # o recorte volta ecoado: a tela nunca deve adivinhar o que pediu, e o
    # download do V3.3 precisa registrar isto na auditoria
    assert corpo["filtros"]["de"] == "2026-01"
    assert corpo["filtros"]["movimento"] == "rec"

    unidade = corpo["linhas"][0]
    assert unidade["chave"] == "RMSPII"
    assert unidade["filhos"][0]["filhos"][0]["nivel"] == "operacao"


def test_numero_vai_como_texto_para_nao_perder_precisao(cliente_v3, cursor):
    """Peso e valor em R$ nao devem passar pelo float do JavaScript. Decimal sai
    como string, e a tela formata."""
    semear(cursor, _semear_entrada, peso="12345.678")
    corpo = cliente_v3.get(
        "/api/matriz",
        params={"de": "2026-01", "ate": "2026-01", "lente": "liq"},
    ).json()
    valor = corpo["total"]["2026-01"]
    assert isinstance(valor, str), f"veio {type(valor).__name__}, esperado string"
    assert Decimal(valor) == Decimal("12345.678")


def test_filtro_invalido_e_400_e_nao_500(cliente_v3):
    """500 aqui esconderia erro do chamador atras de erro do servidor -- e
    manda quem esta depurando olhar o lugar errado."""
    for params, pedaco in (
        ({"de": "2026-01", "ate": "2026-01", "lente": "xpto"}, "lente"),
        ({"de": "2026-01", "ate": "2026-01", "movimento": "xpto"}, "movimento"),
        ({"de": "2026-01", "ate": "2026-01", "faixa": "xpto"}, "faixa"),
        ({"de": "janeiro", "ate": "2026-01"}, "AAAA-MM"),
        ({"de": "2026-03", "ate": "2026-01"}, "invertido"),
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
        params={"de": "2026-01", "ate": "2026-01", "movimento": "exp",
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
        params={"de": "2026-01", "ate": "2026-01", "movimento": "exp",
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
        params={"de": "2026-01", "ate": "2026-01", "movimento": "rec", "lente": "liq"},
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
    assert corpo["filtros"]["de"] == "2026-01"


def test_planilha_e_matriz_usam_o_mesmo_recorte(cliente_v3, cursor):
    """Se a planilha e a Matriz discordassem sobre quais linhas estao no
    recorte, a tela mostraria um numero e baixaria outro."""
    semear(cursor, _semear_entrada, sigla="RMSPII", peso="10.000")
    semear(cursor, _semear_entrada, sigla="CWBIII", gem="0000000002", peso="20.000")

    params = {"de": "2026-01", "ate": "2026-01", "movimento": "rec",
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
        params={"de": "2026-01", "ate": "2026-01", "movimento": "rec",
                "formato": "csv"},
    )
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert "catering_entrada_2026-01_a_2026-01.csv" in \
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
        params={"de": "2026-01", "ate": "2026-01", "formato": "xlsx"},
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
        params={"de": "2026-01", "ate": "2026-01", "formato": "csv", "pagina": 2},
    )
    linhas = resposta.content.decode("utf-8-sig").strip().splitlines()
    assert len(linhas) == 4, "o download deveria trazer as 3 linhas, nao uma pagina"

    ruim = cliente_v3.get(
        "/api/download",
        params={"de": "2026-01", "ate": "2026-01", "formato": "pdf"},
    )
    assert ruim.status_code == 400
    assert "formato" in ruim.json()["detail"]
