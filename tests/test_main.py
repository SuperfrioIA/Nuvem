"""`/health` e o handler global de excecao (Bloco G / G1, continuidade):
Postgres fora do ar precisa aparecer no health, e qualquer excecao crua que
escape de um router precisa virar 500 tratado, nunca traceback pro cliente.

Bloco G / G2: paginas HTML fechadas (gate server-side), /frontend/*.html
bloqueado, /docs fechado e o request id no header de toda resposta."""

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
    # achado da verificacao independente: o ContextVar do request id e
    # resetado pelo middleware antes do handler global rodar -- sem o
    # request.state como fallback, o header saia "-" bem no caso de erro
    # que mais precisa de correlacao no log.
    assert resposta.headers.get("x-request-id") not in (None, "-")


def test_http_exception_existente_nao_muda_de_comportamento(banco_migrado):
    # garante que o handler global nao capturou o que ja tinha handler proprio
    # (HTTPException do FastAPI continua mais especifica, por MRO)
    with TestClient(app, raise_server_exceptions=False) as cliente:
        resposta = cliente.post("/api/admin/login", data={"senha": "senha-errada"})
    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "senha incorreta"}


# --- paginas HTML fechadas (Bloco G / G2) -----------------------------------


def test_pagina_sem_sessao_redireciona_pro_admin(banco_migrado):
    with TestClient(app, follow_redirects=False) as cliente:
        for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
            resposta = cliente.get(pagina)
            assert resposta.status_code in (302, 307), pagina
            assert resposta.headers["location"] == "/admin", pagina


def test_pagina_com_sessao_responde_200(banco_migrado):
    with TestClient(app, follow_redirects=False) as cliente:
        cliente.post("/api/admin/login", data={"senha": os.environ["ADMIN_PASSWORD"]})
        for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
            assert cliente.get(pagina).status_code == 200, pagina


def test_admin_fica_aberto_sem_sessao():
    # e a propria tela de login -- gatear travaria o proprio login
    with TestClient(app, follow_redirects=False) as cliente:
        assert cliente.get("/admin").status_code == 200


def test_frontend_bloqueia_html_direto_mas_no_resto_continua_aberto(banco_migrado):
    with TestClient(app) as cliente:
        assert cliente.get("/frontend/admin.html").status_code == 404
        assert cliente.get("/frontend/cockpit.html").status_code == 404
        # achado da verificacao independente: filesystem case-insensitive
        # (Windows/Mac) deixava passar ADMIN.HTML por acidente do SO, nao da
        # logica -- confere que a checagem em si e case-insensitive
        assert cliente.get("/frontend/ADMIN.HTML").status_code == 404
        assert cliente.get("/frontend/Admin.Html").status_code == 404
        # asset comum (JS/CSS/imagem) continua aberto -- a propria tela de
        # login depende de comum.js carregar antes de autenticar
        assert cliente.get("/frontend/comum.js").status_code == 200


def test_docs_fechado(banco_migrado):
    with TestClient(app) as cliente:
        assert cliente.get("/docs").status_code == 404
        assert cliente.get("/openapi.json").status_code == 404


def test_toda_resposta_tem_request_id(banco_migrado):
    with TestClient(app) as cliente:
        resposta = cliente.get("/health")
    assert resposta.headers.get("x-request-id")
