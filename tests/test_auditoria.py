"""Trilha de auditoria (Bloco G / G2): login/logout, download de arquivo,
mudança de cadastro (armazém/de-para) e decisão de insight aprovado/
descartado -- os pontos que o mapeamento do Bloco G apontou como ausentes.
`ator` é sempre "admin" (senha única, decisão do G1)."""

import os

import psycopg2

from backend import armazenamento
from backend.services import ia_client
from tests import test_laboratorio as tl
from tests.conftest import consultar

cache_limpo = tl.cache_limpo

_RASCUNHO = {
    "nome": "Peso movimentado por cliente",
    "pergunta_negocio": "Quanto cada cliente movimentou em peso no mês?",
    "formula": "Soma do Peso Bruto (kg) das entradas, agrupado por cliente e competência.",
    "riscos": ["cliente fora do cadastro entra no balde 'sem cliente identificado'"],
    "exemplos": ["CLIENTE_1 movimentou 150 kg em 2026-07"],
}


def _resposta_estruturada():
    return {
        "texto": "{}", "dados": _RASCUNHO, "modelo": "claude-sonnet-5",
        "effort": "medium", "tokens_entrada": 20, "tokens_saida": 10,
    }


def _eventos(tipo: str) -> list[tuple]:
    return consultar(
        "SELECT detalhe, ip, ator FROM eventos_auditoria WHERE tipo = %s ORDER BY id",
        (tipo,),
    )


def test_login_sucesso_e_auditado(cliente):
    # a propria fixture `cliente` ja fez o login antes do teste comecar
    eventos = _eventos("login_sucesso")
    assert len(eventos) == 1
    _detalhe, _ip, ator = eventos[0]
    assert ator == "admin"


def test_login_falha_e_auditada(cliente):
    resposta = cliente.post("/api/admin/login", data={"senha": "senha-errada"})
    assert resposta.status_code == 401
    assert len(_eventos("login_falha")) == 1


def test_logout_e_auditado(cliente):
    resposta = cliente.post("/api/admin/logout")
    assert resposta.status_code == 200
    assert len(_eventos("logout")) == 1


def test_armazem_criado_e_auditado(cliente):
    resposta = cliente.post(
        "/api/admin/armazens", data={"nome": "Teste Auditoria", "sigla": "TSTAUD"}
    )
    assert resposta.status_code == 200
    eventos = _eventos("armazem_criado")
    assert len(eventos) == 1
    detalhe, _ip, _ator = eventos[0]
    assert detalhe == {"nome": "Teste Auditoria", "sigla": "TSTAUD"}


def test_depara_criado_e_apagado_sao_auditados(cliente):
    conector_id = consultar("SELECT id FROM conectores WHERE tipo = 'upload_manual'")[0][0]
    armazem_id = consultar("SELECT id FROM armazens LIMIT 1")[0][0]

    criado = cliente.post(
        "/api/admin/depara",
        data={
            "conector_id": conector_id,
            "armazem_na_fonte": "TESTE_AUDITORIA",
            "armazem_id": armazem_id,
        },
    )
    assert criado.status_code == 200
    assert len(_eventos("depara_criado")) == 1

    depara_id = criado.json()["id"]
    apagado = cliente.delete(f"/api/admin/depara/{depara_id}")
    assert apagado.status_code == 200
    eventos = _eventos("depara_apagado")
    assert len(eventos) == 1
    assert eventos[0][0] == {"depara_id": depara_id}


def test_download_de_arquivo_e_auditado(cliente):
    conector_id = consultar("SELECT id FROM conectores WHERE tipo = 'upload_manual'")[0][0]
    caminho = armazenamento.salvar_arquivo(b"conteudo de teste", "arquivo_teste.xlsx")
    # consultar() e so SELECT (nao comita) -- grava direto via cursor avulso
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO execucoes (conector_id, origem, status, arquivo_path) "
            "VALUES (%s, 'manual', 'ok', %s) RETURNING id",
            (conector_id, caminho),
        )
        execucao_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    resposta = cliente.get(f"/api/admin/execucoes/{execucao_id}/arquivo")
    assert resposta.status_code == 200
    eventos = _eventos("download_arquivo_execucao")
    assert len(eventos) == 1
    assert eventos[0][0] == {"execucao_id": execucao_id}


def test_insight_descartado_e_auditado(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post(
        "/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}
    ).json()

    resposta = cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/descartar",
        json={"motivo": "teste de auditoria"},
    )
    assert resposta.status_code == 200
    eventos = _eventos("insight_descartado")
    assert len(eventos) == 1
    assert eventos[0][0] == {"sessao_id": sessao["id"]}


def test_insight_aprovado_e_auditado(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post(
        "/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}
    ).json()

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
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/aprovar", json={"nota": "ok"}
    )
    assert resposta.status_code == 200
    eventos = _eventos("insight_aprovado")
    assert len(eventos) == 1
    assert eventos[0][0] == {"sessao_id": sessao["id"]}
