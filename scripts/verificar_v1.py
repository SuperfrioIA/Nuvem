"""Checklist automatizado da V1 (Bloco G / G3).

Automatiza a verificacao manual que vinha sendo feita a mao, com curl, depois
de cada bloco desde o A: health, gate de login (declarativo desde o G2),
paginas HTML fechadas, `/frontend/*.html` bloqueado, `/docs` fechado, request
id no header. Nao cobre o rate limit de login (`backend/auth.py`) de proposito
-- disparar as 10 falhas necessarias bloquearia o proprio IP por 10 minutos, o
que tornaria o script perigoso de rodar num runbook; esse cenario segue como
teste automatizado isolado em `tests/test_auth.py`, nao aqui. Nao substitui a
suite pytest (que roda contra o codigo, com banco isolado) -- este script roda
contra uma instancia viva (local ou, depois que a Maria decidir subir o
G1+G2+G3, a VM), com HTTP de verdade.

Uso:
    python scripts/verificar_v1.py [URL_BASE]

URL_BASE default: http://localhost:8002. Senha do admin vem de
ADMIN_PASSWORD (mesma variavel que o container usa). Saida: OK/FALHA por
item; codigo de saida 0 se tudo passou, 1 se algo falhou.
"""

import os
import sys

import httpx

_FALHAS: list[str] = []


def _checar(descricao: str, ok: bool, detalhe: str = "") -> None:
    if ok:
        print(f"OK    {descricao}")
    else:
        print(f"FALHA {descricao}" + (f" -- {detalhe}" if detalhe else ""))
        _FALHAS.append(descricao)


def verificar(url_base: str, senha: str) -> None:
    with httpx.Client(base_url=url_base, follow_redirects=False, timeout=10.0) as http:
        resposta = http.get("/health")
        _checar("/health responde 200", resposta.status_code == 200, f"status {resposta.status_code}")
        _checar("resposta traz X-Request-Id", bool(resposta.headers.get("x-request-id")))

        resposta = http.get("/admin")
        _checar("/admin abre sem sessao (e a propria tela de login)", resposta.status_code == 200)

        for rota in ("/docs", "/redoc", "/openapi.json"):
            resposta = http.get(rota)
            _checar(f"{rota} fechado (404)", resposta.status_code == 404, f"status {resposta.status_code}")

        resposta = http.post("/api/admin/login", data={"senha": "senha-propositalmente-errada"})
        _checar("login com senha errada da 401", resposta.status_code == 401, f"status {resposta.status_code}")

        resposta = http.get("/api/admin/conectores")
        _checar("rota protegida sem sessao da 401", resposta.status_code == 401, f"status {resposta.status_code}")

        for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
            resposta = http.get(pagina)
            eh_redirect = resposta.status_code in (302, 307) and resposta.headers.get("location") == "/admin"
            _checar(f"{pagina} sem sessao redireciona pro /admin", eh_redirect, f"status {resposta.status_code}")

        resposta = http.get("/frontend/admin.html")
        _checar("/frontend/admin.html bloqueado (404)", resposta.status_code == 404)
        resposta = http.get("/frontend/ADMIN.HTML")
        _checar("/frontend/ADMIN.HTML bloqueado mesmo em maiuscula (404)", resposta.status_code == 404)
        resposta = http.get("/frontend/comum.js")
        _checar("/frontend/comum.js continua aberto (200)", resposta.status_code == 200)

        resposta = http.post("/api/admin/login", data={"senha": senha})
        logou = resposta.status_code == 200 and "nuvem_sessao" in resposta.cookies
        _checar("login com senha certa autentica e seta cookie", logou, f"status {resposta.status_code}")
        if not logou:
            return

        resposta = http.get("/api/admin/conectores")
        _checar("rota protegida com sessao responde 200", resposta.status_code == 200)

        for pagina in ("/nuvem", "/laboratorio", "/cockpit", "/linhagem"):
            resposta = http.get(pagina)
            _checar(f"{pagina} com sessao responde 200", resposta.status_code == 200)

        http.post("/api/admin/logout")


def main() -> int:
    url_base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
    senha = os.environ.get("ADMIN_PASSWORD")
    if not senha:
        print("erro: defina ADMIN_PASSWORD no ambiente antes de rodar o script")
        return 1

    print(f"Verificando {url_base}...\n")
    try:
        verificar(url_base, senha)
    except httpx.HTTPError as exc:
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
