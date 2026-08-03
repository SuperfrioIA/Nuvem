"""`/health` e o handler global de excecao (Bloco G / G1, continuidade):
Postgres fora do ar precisa aparecer no health, e qualquer excecao crua que
escape de um router precisa virar 500 tratado, nunca traceback pro cliente."""

import os

import psycopg2
from fastapi.testclient import TestClient

from backend.main import app


def test_health_ok_quando_banco_responde(banco_migrado):
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_health_503_quando_banco_indisponivel(banco_migrado, monkeypatch):
    import backend.main as main_module

    def _get_conn_quebrado():
        raise psycopg2.OperationalError("banco fora do ar (teste)")

    with TestClient(app) as cliente:
        monkeypatch.setattr(main_module, "get_conn", _get_conn_quebrado)
        resposta = cliente.get("/health")
    assert resposta.status_code == 503


def test_health_nao_exige_login(banco_migrado):
    # sonda de infraestrutura -- Docker precisa chamar sem cookie de sessao
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
    assert resposta.status_code in (200, 503)


def test_excecao_nao_tratada_vira_500_sem_expor_detalhe(banco_migrado, monkeypatch):
    import backend.routers.admin as admin_module

    mensagem_crua = "falha crua de teste -- nao deveria chegar ao cliente"

    def _get_conn_quebrado():
        raise RuntimeError(mensagem_crua)

    with TestClient(app, raise_server_exceptions=False) as cliente:
        login = cliente.post(
            "/api/admin/login", data={"senha": os.environ["ADMIN_PASSWORD"]}
        )
        assert login.status_code == 200

        monkeypatch.setattr(admin_module, "get_conn", _get_conn_quebrado)
        resposta = cliente.get("/api/admin/conectores")

    assert resposta.status_code == 500
    assert resposta.json() == {"detail": "erro interno"}
    assert mensagem_crua not in resposta.text


def test_http_exception_existente_nao_muda_de_comportamento(banco_migrado):
    # garante que o handler global nao capturou o que ja tinha handler proprio
    # (HTTPException do FastAPI continua mais especifica, por MRO)
    with TestClient(app, raise_server_exceptions=False) as cliente:
        resposta = cliente.post("/api/admin/login", data={"senha": "senha-errada"})
    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "senha incorreta"}
