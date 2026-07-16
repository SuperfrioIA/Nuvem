import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request, Response

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
SECRET_KEY = os.environ["SECRET_KEY"].encode()
COOKIE_NAME = "nuvem_sessao"
SESSAO_DURACAO_SEGUNDOS = 12 * 3600


def _assinar(payload: str) -> str:
    assinatura = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{assinatura}"


def _verificar(token: str) -> bool:
    try:
        payload, assinatura = token.rsplit(".", 1)
    except ValueError:
        return False
    esperada = hmac.new(SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperada, assinatura):
        return False
    return time.time() < int(payload)


def senha_confere(senha: str) -> bool:
    return hmac.compare_digest(senha, ADMIN_PASSWORD)


def criar_sessao(response: Response) -> None:
    expira_em = int(time.time()) + SESSAO_DURACAO_SEGUNDOS
    token = _assinar(str(expira_em))
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", max_age=SESSAO_DURACAO_SEGUNDOS
    )


def encerrar_sessao(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


def autenticado(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    return bool(token) and _verificar(token)


def exigir_login(request: Request) -> None:
    if not autenticado(request):
        raise HTTPException(status_code=401, detail="não autenticado")
