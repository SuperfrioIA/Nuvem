"""Checklist automatizado da V1 (Bloco G / G3).

Automatiza a verificacao manual que vinha sendo feita a mao, com curl, depois
de cada bloco desde o A: health, gate de login (declarativo desde o G2),
paginas HTML fechadas, `/frontend/*.html` bloqueado, `/docs` fechado, request
id no header. Nao cobre o rate limit de login (`backend/auth.py`) de proposito
-- disparar as 10 falhas necessarias bloquearia o proprio IP por 10 minutos, o
que tornaria o script perigoso de rodar num runbook; esse cenario segue como
teste automatizado isolado em `tests/test_auth.py`, nao aqui. Nao substitui a
suite pytest (que roda contra o codigo, com banco isolado) -- este script roda
contra uma instancia viva (local ou VM), com HTTP de verdade.

So stdlib (http.client) de proposito: o Python do HOST que roda o docker
compose nao tem as dependencias do projeto (essas ficam so dentro da imagem,
`scripts/` nem e copiado pro container) -- exigir um `pip install` antes de
rodar um script de verificacao pos-deploy derrotaria o proposito dele.

Uso:
    python3 scripts/verificar_v1.py [URL_BASE]

URL_BASE default: http://localhost:8002. Senha do admin vem de
ADMIN_PASSWORD (mesma variavel que o container usa). Saida: OK/FALHA por
item; codigo de saida 0 se tudo passou, 1 se algo falhou.
"""

import http.client
import os
import sys
from urllib.parse import urlencode, urlsplit

_FALHAS: list[str] = []


def _checar(descricao: str, ok: bool, detalhe: str = "") -> None:
    if ok:
        print(f"OK    {descricao}")
    else:
        print(f"FALHA {descricao}" + (f" -- {detalhe}" if detalhe else ""))
        _FALHAS.append(descricao)


def _conexao(hostname: str, porta: int | None, https: bool) -> http.client.HTTPConnection:
    classe = http.client.HTTPSConnection if https else http.client.HTTPConnection
    return classe(hostname, porta, timeout=10)


def _requisitar(hostname, porta, https, metodo, caminho, corpo=None, cookie=None):
    conn = _conexao(hostname, porta, https)
    try:
        cabecalhos = {}
        if cookie:
            cabecalhos["Cookie"] = cookie
        if corpo is not None:
            cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        conn.request(metodo, caminho, body=corpo, headers=cabecalhos)
        resposta = conn.getresponse()
        resposta.read()
        cabecalhos_resposta = {chave.lower(): valor for chave, valor in resposta.getheaders()}
        return resposta.status, cabecalhos_resposta
    finally:
        conn.close()


def verificar(url_base: str, senha: str) -> None:
    partes = urlsplit(url_base)
    https = partes.scheme == "https"
    hostname, porta = partes.hostname, partes.port

    def get(caminho, cookie=None):
        return _requisitar(hostname, porta, https, "GET", caminho, cookie=cookie)

    def post(caminho, dados, cookie=None):
        return _requisitar(hostname, porta, https, "POST", caminho, corpo=urlencode(dados), cookie=cookie)

    status, cabecalhos = get("/health")
    _checar("/health responde 200", status == 200, f"status {status}")
    _checar("resposta traz X-Request-Id", bool(cabecalhos.get("x-request-id")))

    status, _ = get("/admin")
    _checar("/admin abre sem sessao (e a propria tela de login)", status == 200)

    for rota in ("/docs", "/redoc", "/openapi.json"):
        status, _ = get(rota)
        _checar(f"{rota} fechado (404)", status == 404, f"status {status}")

    status, _ = post("/api/admin/login", {"senha": "senha-propositalmente-errada"})
    _checar("login com senha errada da 401", status == 401, f"status {status}")

    status, _ = get("/api/admin/conectores")
    _checar("rota protegida sem sessao da 401", status == 401, f"status {status}")

    for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
        status, cabecalhos = get(pagina)
        eh_redirect = status in (302, 307) and cabecalhos.get("location") == "/admin"
        _checar(f"{pagina} sem sessao redireciona pro /admin", eh_redirect, f"status {status}")

    status, _ = get("/frontend/admin.html")
    _checar("/frontend/admin.html bloqueado (404)", status == 404)
    status, _ = get("/frontend/ADMIN.HTML")
    _checar("/frontend/ADMIN.HTML bloqueado mesmo em maiuscula (404)", status == 404)
    status, _ = get("/frontend/comum.js")
    _checar("/frontend/comum.js continua aberto (200)", status == 200)

    status, cabecalhos = post("/api/admin/login", {"senha": senha})
    cookie = cabecalhos.get("set-cookie", "").split(";", 1)[0] or None
    logou = status == 200 and cookie is not None
    _checar("login com senha certa autentica e seta cookie", logou, f"status {status}")
    if not logou:
        return

    status, _ = get("/api/admin/conectores", cookie=cookie)
    _checar("rota protegida com sessao responde 200", status == 200)

    for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
        status, _ = get(pagina, cookie=cookie)
        _checar(f"{pagina} com sessao responde 200", status == 200)

    post("/api/admin/logout", {}, cookie=cookie)


def main() -> int:
    url_base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
    senha = os.environ.get("ADMIN_PASSWORD")
    if not senha:
        print("erro: defina ADMIN_PASSWORD no ambiente antes de rodar o script")
        return 1

    print(f"Verificando {url_base}...\n")
    try:
        verificar(url_base, senha)
    except OSError as exc:
        print(f"FALHA nao foi possivel falar com {url_base} -- {exc}")
        return 1

    print()
    if _FALHAS:
        print(f"{len(_FALHAS)} item(ns) com FALHA:")
        for item in _FALHAS:
            print(f"  - {item}")
        return 1

    print("Tudo OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
