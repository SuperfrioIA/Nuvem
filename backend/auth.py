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


# Rate limit do login (Bloco G / G2): senha unica, sem identidade por pessoa,
# entao o controle e por IP de origem. Calibrado com a Maria pra nao travar o
# CSC inteiro se estiver atras do mesmo IP da rede da SuperFrio: 10 falhas
# tranca por 10 min, nao 5/15 -- um lockout mais agressivo travaria o time
# inteiro por uma pessoa errando a senha. Em memoria, de proposito (sem
# persistencia): perde o estado num restart do container, mas e proporcional
# a uma ferramenta interna de CSC, nao defesa contra atacante determinado.
_TENTATIVAS_MAX = 10
_JANELA_SEGUNDOS = 10 * 60
_BLOQUEIO_SEGUNDOS = 10 * 60

_falhas_por_ip: dict[str, list[float]] = {}
_bloqueado_ate: dict[str, float] = {}


def ip_do_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def verificar_bloqueio_login(request: Request) -> None:
    ip = ip_do_cliente(request)
    ate = _bloqueado_ate.get(ip)
    if ate is not None and time.time() < ate:
        raise HTTPException(status_code=429, detail="muitas tentativas -- tente novamente mais tarde")


def registrar_falha_login(request: Request) -> None:
    ip = ip_do_cliente(request)
    agora = time.time()
    tentativas = [t for t in _falhas_por_ip.get(ip, []) if agora - t < _JANELA_SEGUNDOS]
    tentativas.append(agora)
    _falhas_por_ip[ip] = tentativas
    if len(tentativas) >= _TENTATIVAS_MAX:
        _bloqueado_ate[ip] = agora + _BLOQUEIO_SEGUNDOS


def registrar_sucesso_login(request: Request) -> None:
    ip = ip_do_cliente(request)
    _falhas_por_ip.pop(ip, None)
    _bloqueado_ate.pop(ip, None)


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
