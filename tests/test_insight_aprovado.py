"""Promoção de insight para KPI (Bloco E / V1.6). Postgres real; provedor de
IA sempre mockado via `ia_client.enviar_mensagem`.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ia_client, insight_aprovado, laboratorio, laboratorio_chat
from tests import test_laboratorio as tl

cache_limpo = tl.cache_limpo

_RASCUNHO = {
    "nome": "Peso movimentado por cliente",
    "pergunta_negocio": "Quanto cada cliente movimentou em peso no mês?",
    "formula": "Soma do Peso Bruto (kg) das entradas, agrupado por cliente e competência.",
    "riscos": ["cliente fora do cadastro entra no balde 'sem cliente identificado'"],
    "exemplos": ["CLIENTE_1 movimentou 150 kg em 2026-07"],
}


def _resposta_estruturada(dados=None):
    return {
        "texto": "{}",
        "dados": dados or _RASCUNHO,
        "modelo": "claude-sonnet-5",
        "effort": "medium",
        "tokens_entrada": 200,
        "tokens_saida": 60,
    }


def _sessao_com_chat(monkeypatch, cursor, cliente="SAPORE"):
    tl._arquivo_integrado(
        monkeypatch, linhas=[tl._linha_integrada(cliente=cliente, peso=150.0)]
    )
    sessao = laboratorio.perfilar_selecao(cursor, ["item-016"])
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: {
        "texto": "análise feita", "dados": None, "modelo": "claude-sonnet-5",
        "effort": "medium", "tokens_entrada": 10, "tokens_saida": 5,
    })
    laboratorio_chat.perguntar(cursor, sessao, "Sugira um KPI de peso por cliente.")
    return laboratorio.obter_sessao(cursor, sessao["id"])


# --- gerar_especificacao -------------------------------------------------------


def test_gerar_especificacao_sem_mensagem_falha(monkeypatch, cursor):
    tl._arquivo_integrado(monkeypatch)
    sessao = laboratorio.perfilar_selecao(cursor, ["item-016"])
    with pytest.raises(insight_aprovado.InsightAprovadoError, match="converse antes"):
        insight_aprovado.gerar_especificacao(cursor, sessao)


def test_gerar_especificacao_combina_ia_com_parte_deterministica_do_perfil(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_estruturada())

    especificacao = insight_aprovado.gerar_especificacao(cursor, sessao)

    # da IA (rascunho, revisao humana)
    assert especificacao["nome"] == _RASCUNHO["nome"]
    assert especificacao["formula"] == _RASCUNHO["formula"]
    # do perfil (deterministico, nunca da IA)
    assert especificacao["fontes"][0]["arquivo"] == "ENTRADA_MERCADORIAS_016_2607.xlsx"
    assert especificacao["fontes"][0]["origem"] == "RMSPII/016 (RMSPIV)"
    assert "peso_bruto_movimentado" in especificacao["conceitos"]
    assert "kg" in especificacao["unidades"]
    assert especificacao["dimensoes"] == ["período", "filial", "cliente"]
    assert especificacao["historico_conversa"][0]["papel"] == "usuario"


def test_gerar_especificacao_nunca_expõe_cliente_em_claro_no_que_foi_pra_ia(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor, cliente="SAPORE")
    capturado = {}

    def _capturar(**kw):
        capturado.update(kw)
        return _resposta_estruturada()

    monkeypatch.setattr(ia_client, "enviar_mensagem", _capturar)
    insight_aprovado.gerar_especificacao(cursor, sessao)

    assert "SAPORE" not in str(capturado["mensagens"])
    assert capturado["schema"]["required"] == ["nome", "pergunta_negocio", "formula", "riscos", "exemplos"]


# --- aprovar / descartar --------------------------------------------------------


def test_aprovar_grava_especificacao_e_muda_status(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_estruturada())

    especificacao = insight_aprovado.aprovar(cursor, sessao["id"], nota="revisado com a diretoria")

    assert especificacao["nome"] == _RASCUNHO["nome"]
    atualizada = laboratorio.obter_sessao(cursor, sessao["id"])
    assert atualizada["status"] == "aprovada"
    assert atualizada["decisao_nota"] == "revisado com a diretoria"
    assert atualizada["decidido_em"] is not None
    assert atualizada["especificacao"]["nome"] == _RASCUNHO["nome"]


def test_aprovar_sessao_ja_decidida_falha(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_estruturada())
    insight_aprovado.aprovar(cursor, sessao["id"])

    with pytest.raises(insight_aprovado.InsightAprovadoError, match="definitiva"):
        insight_aprovado.aprovar(cursor, sessao["id"])


def test_aprovar_sessao_inexistente_falha(cursor):
    with pytest.raises(insight_aprovado.InsightAprovadoError, match="não encontrada"):
        insight_aprovado.aprovar(cursor, 99999)


def test_aprovar_quando_ia_falha_vira_erro_tratado_e_nao_decide_a_sessao(monkeypatch, cursor):
    """Achado da verificação independente: sem tratamento, falha da IA aqui
    subia como excecao crua (HTTP 500 no endpoint) em vez do 400 tratado que
    o resto do Laboratório sempre devolve."""
    sessao = _sessao_com_chat(monkeypatch, cursor)

    def _indisponivel(**kw):
        raise ia_client.IAIndisponivelError("fora do ar")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _indisponivel)
    with pytest.raises(insight_aprovado.InsightAprovadoError, match="fora do ar"):
        insight_aprovado.aprovar(cursor, sessao["id"])

    # a sessao nao fica presa num estado intermediario -- so decide se a
    # especificacao sair
    ainda_em_analise = laboratorio.obter_sessao(cursor, sessao["id"])
    assert ainda_em_analise["status"] == "em_analise"
    assert ainda_em_analise["especificacao"] is None


def test_descartar_muda_status_e_grava_motivo(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)
    insight_aprovado.descartar(cursor, sessao["id"], motivo="indicador já existe no cockpit")

    atualizada = laboratorio.obter_sessao(cursor, sessao["id"])
    assert atualizada["status"] == "descartada"
    assert atualizada["decisao_nota"] == "indicador já existe no cockpit"
    assert atualizada["especificacao"] is None


def test_descartar_nao_chama_a_ia(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)

    def _falhar(**kw):
        raise AssertionError("descartar não deveria chamar a IA")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _falhar)
    insight_aprovado.descartar(cursor, sessao["id"])


def test_descartar_sessao_ja_decidida_falha(monkeypatch, cursor):
    sessao = _sessao_com_chat(monkeypatch, cursor)
    insight_aprovado.descartar(cursor, sessao["id"])
    with pytest.raises(insight_aprovado.InsightAprovadoError, match="definitiva"):
        insight_aprovado.descartar(cursor, sessao["id"])


# --- endpoints -----------------------------------------------------------------


def test_endpoint_aprovar_e_descartar_sem_login_dao_401(banco_migrado):
    with TestClient(app) as c:
        assert c.post("/api/admin/laboratorio/sessoes/1/aprovar", json={}).status_code == 401
        assert c.post("/api/admin/laboratorio/sessoes/1/descartar", json={}).status_code == 401


def test_endpoint_aprovar_via_http(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post("/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}).json()

    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: {
        "texto": "ok", "dados": None, "modelo": "claude-sonnet-5",
        "effort": "medium", "tokens_entrada": 5, "tokens_saida": 5,
    })
    cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/mensagens",
        json={"pergunta": "Sugira um KPI.", "mensagem_sugerida": None},
    )

    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_estruturada())
    resposta = cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/aprovar", json={"nota": "ok pra implementar"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == _RASCUNHO["nome"]

    detalhe = cliente.get(f"/api/admin/laboratorio/sessoes/{sessao['id']}").json()
    assert detalhe["status"] == "aprovada"


def test_endpoint_aprovar_quando_ia_falha_da_400_nao_500(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post("/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}).json()

    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: {
        "texto": "ok", "dados": None, "modelo": "claude-sonnet-5",
        "effort": "medium", "tokens_entrada": 5, "tokens_saida": 5,
    })
    cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/mensagens",
        json={"pergunta": "Sugira um KPI.", "mensagem_sugerida": None},
    )

    def _falhar(**kw):
        raise ia_client.IAIndisponivelError("fora do ar")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _falhar)
    resposta = cliente.post(f"/api/admin/laboratorio/sessoes/{sessao['id']}/aprovar", json={})
    assert resposta.status_code == 400
    assert "fora do ar" in resposta.json()["detail"]


def test_endpoint_descartar_via_http(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post("/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}).json()

    resposta = cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/descartar", json={"motivo": "não é prioridade"}
    )
    assert resposta.status_code == 200
    detalhe = cliente.get(f"/api/admin/laboratorio/sessoes/{sessao['id']}").json()
    assert detalhe["status"] == "descartada"
