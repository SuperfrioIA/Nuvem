"""Testes de unidade do inventario do DataHub (Lote P2). graph_datahub.listar_itens
e sempre mockado -- nenhuma chamada real ao SharePoint/Microsoft Graph.
"""

import pytest

from backend.services import graph_datahub, inventario_datahub


@pytest.fixture(autouse=True)
def cache_limpo():
    """O cache e global de processo -- zera antes e depois de cada teste, senao
    um teste herda o resumo do anterior."""
    estado_inicial = {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}
    inventario_datahub._cache.update(estado_inicial)
    yield
    inventario_datahub._cache.update(estado_inicial)


def _item_pasta(id_, nome):
    return {"id": id_, "name": nome, "folder": {}}


def _item_arquivo(
    nome, tamanho=100, modificado_em="2026-07-01T00:00:00Z", id_="item-fake", web_url="https://exemplo/arquivo"
):
    return {
        "name": nome,
        "file": {},
        "size": tamanho,
        "lastModifiedDateTime": modificado_em,
        "id": id_,
        "webUrl": web_url,
    }


def test_estado_inicial_nunca_sincronizado():
    estado = inventario_datahub.status()
    assert estado == {"sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None}


def test_status_nunca_chama_o_graph(monkeypatch):
    def _levanta(item_id=None):
        raise AssertionError("status() nao deveria chamar listar_itens")

    monkeypatch.setattr(graph_datahub, "listar_itens", _levanta)
    inventario_datahub.status()  # nao deve levantar


def test_recursao_conta_arquivos_e_pastas_em_subpastas(monkeypatch):
    arvore = {
        None: [_item_pasta("f1", "ENTRADA"), _item_arquivo("raiz.xlsx")],
        "f1": [_item_pasta("f2", "ENTRADA MERCADORIAS"), _item_arquivo("a.xlsx")],
        "f2": [_item_arquivo("b.csv"), _item_arquivo("c.csv")],
    }
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arvore[item_id])

    resultado = inventario_datahub.sincronizar()

    assert resultado["ok"] is True
    assert resultado["mensagem_erro"] is None
    resumo = resultado["resumo"]
    assert resumo["total_arquivos"] == 4
    assert resumo["total_pastas"] == 2
    assert resumo["pastas"] == ["ENTRADA", "ENTRADA/ENTRADA MERCADORIAS"]


def test_extensoes_contadas_corretamente(monkeypatch):
    arvore = {
        None: [_item_arquivo("a.xlsx"), _item_arquivo("b.xlsx"), _item_arquivo("c.csv")],
    }
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arvore[item_id])

    resultado = inventario_datahub.sincronizar()
    assert resultado["resumo"]["extensoes"] == {"xlsx": 2, "csv": 1}


def test_arquivos_recentes_ordenados_e_limitados(monkeypatch):
    arquivos = [
        _item_arquivo(f"arquivo_{i}.xlsx", modificado_em=f"2026-07-{i:02d}T00:00:00Z")
        for i in range(1, 13)  # 12 arquivos, dias 01..12
    ]
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arquivos if item_id is None else [])

    resultado = inventario_datahub.sincronizar()
    recentes = resultado["resumo"]["arquivos_recentes"]
    assert len(recentes) == 10
    assert [r["nome"] for r in recentes] == [f"arquivo_{i}.xlsx" for i in range(12, 2, -1)]


def test_arquivo_inclui_id_e_web_url(monkeypatch):
    """Lote P2.1: id (pro download do P3) e web_url (link no painel) precisam
    sobreviver do item bruto do Graph ate o arquivo do resumo."""
    arvore = {
        None: [_item_arquivo("a.xlsx", id_="01ABCDEF", web_url="https://superfrio.sharepoint.com/a.xlsx")]
    }
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arvore[item_id])

    resultado = inventario_datahub.sincronizar()
    arquivo = resultado["resumo"]["arquivos_recentes"][0]
    assert arquivo["id"] == "01ABCDEF"
    assert arquivo["web_url"] == "https://superfrio.sharepoint.com/a.xlsx"


def test_resumo_guarda_lista_completa_de_arquivos(monkeypatch):
    """Lote P3: 'arquivos' e a lista de permissao pro download por item_id --
    tem que conter todo mundo, nao so os _MAX_ARQUIVOS_RECENTES."""
    arquivos = [
        _item_arquivo(f"arquivo_{i}.xlsx", modificado_em=f"2026-07-{i:02d}T00:00:00Z", id_=f"id-{i}")
        for i in range(1, 13)  # 12 arquivos, mais que os 10 recentes
    ]
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arquivos if item_id is None else [])

    resultado = inventario_datahub.sincronizar()
    lista = resultado["resumo"]["arquivos"]
    assert len(lista) == 12
    assert {a["id"] for a in lista} == {f"id-{i}" for i in range(1, 13)}


# --- persistencia da sincronizacao (Bloco C / V1.3) ---------------------------


def _estado_ok(total=3):
    from datetime import datetime, timezone

    return {
        "sincronizado_em": datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
        "ok": True,
        "mensagem_erro": None,
        "resumo": {"total_arquivos": total, "arquivos": [_item_arquivo("a.xlsx")]},
    }


def test_salvar_e_carregar_persistido(cursor):
    estado = _estado_ok()
    inventario_datahub.salvar_persistido(cursor, estado)

    sincronizado_em, resumo = inventario_datahub.carregar_persistido(cursor)
    assert sincronizado_em == estado["sincronizado_em"]
    assert resumo == estado["resumo"]


def test_salvar_ignora_estado_com_erro_ou_sem_resumo(cursor):
    inventario_datahub.salvar_persistido(cursor, {"ok": False, "resumo": {"x": 1}, "sincronizado_em": None})
    inventario_datahub.salvar_persistido(cursor, {"ok": True, "resumo": None, "sincronizado_em": None})
    assert inventario_datahub.carregar_persistido(cursor) == (None, None)


def test_carregar_persistido_pega_a_ultima_sincronizacao(cursor):
    inventario_datahub.salvar_persistido(cursor, _estado_ok(total=1))
    inventario_datahub.salvar_persistido(cursor, _estado_ok(total=2))
    _, resumo = inventario_datahub.carregar_persistido(cursor)
    assert resumo["total_arquivos"] == 2


def test_restaurar_reidrata_cache_vazio():
    estado = _estado_ok()
    inventario_datahub.restaurar(estado["sincronizado_em"], estado["resumo"])

    atual = inventario_datahub.status()
    assert atual["ok"] is True
    assert atual["resumo"] == estado["resumo"]
    assert atual["sincronizado_em"] == estado["sincronizado_em"]


def test_restaurar_nao_sobrescreve_sincronizacao_do_processo():
    inventario_datahub._cache.update(
        {"sincronizado_em": "agora", "ok": True, "mensagem_erro": None, "resumo": {"total_arquivos": 9}}
    )
    inventario_datahub.restaurar("antes", {"total_arquivos": 1})
    assert inventario_datahub.status()["resumo"] == {"total_arquivos": 9}


def test_restaurar_sem_persistido_nao_muda_nada():
    inventario_datahub.restaurar(None, None)
    assert inventario_datahub.status() == {
        "sincronizado_em": None, "ok": None, "mensagem_erro": None, "resumo": None,
    }


def test_erro_preserva_resumo_anterior(monkeypatch):
    arvore_ok = {None: [_item_arquivo("a.xlsx")]}
    monkeypatch.setattr(graph_datahub, "listar_itens", lambda item_id=None: arvore_ok[item_id])
    primeira = inventario_datahub.sincronizar()
    assert primeira["ok"] is True

    def _falha(item_id=None):
        raise graph_datahub.GraphAcessoNegadoError("acesso negado (simulado)")

    monkeypatch.setattr(graph_datahub, "listar_itens", _falha)
    segunda = inventario_datahub.sincronizar()

    assert segunda["ok"] is False
    assert "acesso negado" in segunda["mensagem_erro"]
    assert segunda["resumo"] == primeira["resumo"]
    assert segunda["sincronizado_em"] == primeira["sincronizado_em"]
