"""backend/auth.py nunca tinha teste direto (Bloco G / G2): assinatura e
expiracao do cookie de sessao, e o rate limit novo do login."""

import os
import time

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app


class _RequestFalso:
    """Fica so com o que auth.py realmente le de Request -- request.client.host."""

    def __init__(self, ip: str | None):
        self.client = None if ip is None else type("Client", (), {"host": ip})()


@pytest.fixture(autouse=True)
def _rate_limit_limpo():
    auth._falhas_por_ip.clear()
    auth._bloqueado_ate.clear()
    yield
    auth._falhas_por_ip.clear()
    auth._bloqueado_ate.clear()


# --- cookie assinado ---------------------------------------------------------


def test_token_com_expiracao_futura_e_valido():
    expira_em = int(time.time()) + 3600
    assert auth._verificar(auth._assinar(str(expira_em))) is True


def test_token_expirado_e_invalido():
    expira_em = int(time.time()) - 1
    assert auth._verificar(auth._assinar(str(expira_em))) is False


def test_token_com_assinatura_adulterada_e_invalido():
    token = auth._assinar(str(int(time.time()) + 3600))
    ultimo = token[-1]
    adulterado = token[:-1] + ("0" if ultimo != "0" else "1")
    assert auth._verificar(adulterado) is False


def test_token_mal_formado_e_invalido():
    assert auth._verificar("sem-ponto-nenhum") is False


def test_senha_confere_e_senha_errada_nao():
    assert auth.senha_confere(os.environ["ADMIN_PASSWORD"]) is True
    assert auth.senha_confere("senha-errada-de-teste") is False


# --- ip_do_cliente ------------------------------------------------------------


def test_ip_do_cliente_extrai_host():
    assert auth.ip_do_cliente(_RequestFalso("10.1.1.1")) == "10.1.1.1"


def test_ip_do_cliente_sem_client_devolve_desconhecido():
    assert auth.ip_do_cliente(_RequestFalso(None)) == "desconhecido"


# --- rate limit do login (funcoes puras) -------------------------------------


def test_rate_limit_bloqueia_apos_maximo_de_falhas():
    req = _RequestFalso("10.2.2.1")
    for _ in range(auth._TENTATIVAS_MAX):
        auth.verificar_bloqueio_login(req)  # nao levanta ainda
        auth.registrar_falha_login(req)
    with pytest.raises(HTTPException) as exc:
        auth.verificar_bloqueio_login(req)
    assert exc.value.status_code == 429


def test_rate_limit_sucesso_reseta_o_contador():
    req = _RequestFalso("10.2.2.2")
    for _ in range(auth._TENTATIVAS_MAX - 1):
        auth.registrar_falha_login(req)
    auth.registrar_sucesso_login(req)
    auth.verificar_bloqueio_login(req)  # nao levanta: contador foi zerado


def test_rate_limit_e_por_ip_um_nao_interfere_no_outro():
    bloqueado, livre = _RequestFalso("10.2.2.3"), _RequestFalso("10.2.2.4")
    for _ in range(auth._TENTATIVAS_MAX):
        auth.registrar_falha_login(bloqueado)
    with pytest.raises(HTTPException):
        auth.verificar_bloqueio_login(bloqueado)
    auth.verificar_bloqueio_login(livre)  # ip diferente, nao levanta


# --- rate limit fim-a-fim, pelo endpoint --------------------------------------


def test_login_bloqueia_apos_muitas_falhas_seguidas(banco_migrado):
    with TestClient(app) as cliente:
        for _ in range(auth._TENTATIVAS_MAX):
            resposta = cliente.post("/api/admin/login", data={"senha": "senha-errada"})
            assert resposta.status_code == 401
        bloqueado = cliente.post("/api/admin/login", data={"senha": "senha-errada"})
        assert bloqueado.status_code == 429
        # nem com a senha certa -- o bloqueio vale pro IP, nao pra tentativa
        ainda_bloqueado = cliente.post(
            "/api/admin/login", data={"senha": os.environ["ADMIN_PASSWORD"]}
        )
        assert ainda_bloqueado.status_code == 429
