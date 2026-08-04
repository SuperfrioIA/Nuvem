"""Trilha de auditoria (Bloco G / G2, V1.8) -- eventos_auditoria: quem, quando,
o que. Cobre só os pontos que o mapeamento do bloco apontou como ausentes
(login/logout, download de arquivo, mudança de cadastro, decisão de insight)
-- não é auditoria exaustiva de todo endpoint.

Servico puro (so SQL, sem FastAPI) -- quem monta `ip` a partir do Request e
`auth.ip_do_cliente`. `ator` e sempre "admin" por ora: a autenticacao do
projeto e senha unica, sem identidade por pessoa (mesma limitacao declarada em
`laboratorio.py`); a coluna existe pronta pra quando houver identidade real.
"""

import json

_ATOR_PADRAO = "admin"


def registrar(cur, tipo: str, *, detalhe: dict | None = None, ip: str | None = None, ator: str = _ATOR_PADRAO) -> None:
    cur.execute(
        "INSERT INTO eventos_auditoria (tipo, detalhe, ip, ator) VALUES (%s, %s, %s, %s)",
        (tipo, json.dumps(detalhe or {}, ensure_ascii=False), ip, ator),
    )
