"""A sessao: cookie assinado, e o papel lido do banco a cada request.

## O cookie carrega o login. O papel, NAO.

O cookie diz **quem** ("login e validade, assinados"). O que a pessoa pode e
consultado em `cat_usuarios` a cada request.

Isso e a diferenca entre revogar acesso agora e revogar acesso "em ate 12
horas". Se o papel viajasse no cookie -- que e o atalho barato, porque evita uma
consulta -- rebaixar um admin para visualizador, ou desativar quem saiu da
empresa, so faria efeito quando o cookie expirasse. O crachá continuaria
valendo depois de a pessoa ser desligada.

O custo e uma consulta curta por request autenticado. Numa ferramenta interna de
CSC isso e barato; num sistema com tráfego seria hora de cache com invalidacao
-- e nao de mover o papel para dentro do cookie.

## Assinatura, e nao criptografia

HMAC-SHA256 sobre `"<expira>:<login>"`. O conteudo e legivel para quem tem o
cookie -- e nao ha nada secreto nele: e o proprio login de quem esta logado.
O que a assinatura impede e **forjar**: trocar o login por outro, ou empurrar a
validade para frente, invalida a assinatura.

A validade e verificada no servidor, dentro do payload assinado. `max_age` do
cookie sozinho nao serve: ele e uma instrucao ao navegador, e um cliente que
guarde o cookie por mais tempo continuaria entrando.

## Chave propria, obrigatoria

`CAT_SECRET_KEY`, e nao a `SECRET_KEY` da V2. Chave compartilhada significa que
um vazamento da V2 (congelada, e um dia removida da VM) passa a permitir forjar
sessao da V3.

Sem a variavel, o modulo levanta erro **quando a sessao e usada** -- e nao no
import. A diferenca importa: com erro no import, o app nao sobe, o `/health`
morre junto e o sintoma chega como "container nao fica de pe", sem dizer o que
falta. Com erro no uso, o `/health` responde, o container fica saudavel e o erro
que aparece no log nomeia a variavel ausente.

## `secure` desligado por padrao, e declarado

A VM serve **HTTP puro** hoje (porta 8002, sem TLS). Com `secure=True` o
navegador nao devolveria o cookie e o login simplesmente nao funcionaria em
producao -- por isso o padrao e desligado, controlado por `CAT_COOKIE_SECURE`.

Isto e uma fraqueza real, nao um detalhe: em HTTP, quem estiver no caminho da
rede le o cookie. E aceitavel porque a rede e interna e o dado nao e credencial
de terceiros, e fica **registrado como pendencia** -- no dia em que houver HTTPS,
liga a variavel. `httponly` e `samesite=lax` ficam ligados sempre, porque nao
dependem de TLS: cortam leitura por JavaScript e envio em request de outro site.
"""

import hashlib
import hmac
import logging
import os
import time

from fastapi import HTTPException, Request, Response

from catering.seguranca import usuarios

logger = logging.getLogger(__name__)

COOKIE = "cat_sessao"
DURACAO_SEGUNDOS = 12 * 3600  # um dia de trabalho, como na V2


def _chave() -> bytes:
    """Lida a cada uso, e nao no import -- ver docstring."""
    bruta = os.environ.get("CAT_SECRET_KEY") or ""
    if not bruta.strip():
        raise RuntimeError(
            "CAT_SECRET_KEY ausente -- a sessao da V3 exige chave propria, "
            "separada da SECRET_KEY da V2"
        )
    return bruta.encode("utf-8")


def _cookie_seguro() -> bool:
    return os.environ.get("CAT_COOKIE_SECURE", "0").strip().lower() in (
        "1", "true", "sim", "yes"
    )


def _assinar(payload: str) -> str:
    assinatura = hmac.new(_chave(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{assinatura}"


def _abrir(token):
    """Login de dentro do token, se a assinatura confere e nao expirou."""
    if not token:
        return None
    try:
        payload, assinatura = token.rsplit(".", 1)
    except ValueError:
        return None
    esperada = hmac.new(
        _chave(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(esperada, assinatura):
        return None
    expira, _, login = payload.partition(":")
    try:
        if time.time() >= int(expira):
            return None
    except ValueError:
        return None
    return login or None


def criar(response: Response, usuario) -> None:
    expira = int(time.time()) + DURACAO_SEGUNDOS
    response.set_cookie(
        COOKIE,
        _assinar(f"{expira}:{usuario.login}"),
        max_age=DURACAO_SEGUNDOS,
        httponly=True,
        samesite="lax",
        secure=_cookie_seguro(),
    )


def encerrar(response: Response) -> None:
    response.delete_cookie(COOKIE)


def usuario_atual(request: Request):
    """`Usuario` da sessao, com o papel **do banco**; `None` se nao ha sessao
    valida, se o login sumiu da tabela ou se a conta foi desativada."""
    login = _abrir(request.cookies.get(COOKIE))
    if not login:
        return None
    usuario = usuarios.buscar(login)
    if usuario is None:
        # cookie valido de um login que nao existe mais. Nao e erro: e conta
        # removida com sessao ainda aberta no navegador.
        logger.info("sessao de login inexistente: %s", login)
        return None
    if not usuario.ativo:
        logger.info("sessao de usuario inativo: %s", login)
        return None
    return usuario


def exigir_login(request: Request):
    """Dependencia do FastAPI: devolve o `Usuario` ou levanta 401."""
    usuario = usuario_atual(request)
    if usuario is None:
        raise HTTPException(status_code=401, detail="sessao ausente ou expirada")
    return usuario


def exigir_admin(request: Request):
    """Dependencia do FastAPI: 401 sem sessao, **403** com sessao de
    visualizador.

    Os dois codigos dizem coisas diferentes, e a tela precisa da diferenca: 401 e
    "faca login" (a tela redireciona), 403 e "voce esta logado e isto nao e seu"
    (a tela mostra a recusa). Responder 401 nos dois casos mandaria o
    visualizador para a tela de login, onde ele entraria de novo, para ser
    recusado de novo."""
    usuario = exigir_login(request)
    if not usuario.admin:
        logger.info("acesso de admin recusado para %s (%s)", usuario.login, usuario.papel)
        raise HTTPException(status_code=403, detail="restrito a administradores")
    return usuario
