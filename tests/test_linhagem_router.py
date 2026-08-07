"""Testes dos endpoints /api/admin/linhagem/* (Bloco F / V1.7), via TestClient.

A cadeia recebida -> execucao -> arquivo ja esta coberta em test_linhagem.py
contra o servico direto -- aqui so autenticacao e encaixe HTTP.
"""

from fastapi.testclient import TestClient

from backend.main import app


def test_celulas_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get(
            "/api/admin/linhagem/celulas",
            params={"metrica": "peso_bruto_entrada", "competencia": "2026-07"},
        )
    assert resposta.status_code == 401


def test_origem_sem_login_da_401(banco_migrado):
    with TestClient(app) as c:
        resposta = c.get("/api/admin/linhagem/celulas/1")
    assert resposta.status_code == 401


def test_celulas_sem_dado_devolve_lista_vazia(cliente):
    resposta = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "peso_bruto_entrada", "competencia": "2026-07"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["celulas"] == []


def test_celulas_metrica_invalida_da_400(cliente):
    resposta = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "nao_existe", "competencia": "2026-07"},
    )
    assert resposta.status_code == 400
    assert "nao cadastrada" in resposta.json()["detail"]


def test_celulas_competencia_invalida_da_400(cliente):
    resposta = cliente.get(
        "/api/admin/linhagem/celulas",
        params={"metrica": "peso_bruto_entrada", "competencia": "julho/2026"},
    )
    assert resposta.status_code == 400
    assert "AAAA-MM" in resposta.json()["detail"]


def test_origem_celula_inexistente_da_404(cliente):
    resposta = cliente.get("/api/admin/linhagem/celulas/999999")
    assert resposta.status_code == 404
    assert "nao encontrada" in resposta.json()["detail"]
