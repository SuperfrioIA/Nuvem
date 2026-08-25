"""Auditoria: quem baixou o que, com qual recorte.

## Escopo

Somente **login e download** (Maria, 24/ago/2026). Consulta a consulta nao --
gera volume e ninguem le, e auditoria que ninguem le deixa de ser auditoria e
passa a ser custo de escrita.

## Conexao propria, e commit imediato

O download e um *stream*: ele pode morrer no meio (rede, navegador fechado,
erro no meio da leitura). Se o registro vivesse na mesma transacao da consulta,
uma falha apagaria o proprio rastro da tentativa -- e o caso que mais interessa
numa auditoria e justamente o que deu errado.

Por isso: `abrir()` grava e commita **antes** de a primeira linha sair, e
`fechar()`/`falhar()` atualizam depois. Mesmo padrao do `cat_cargas`, pela mesma
razao.

## `usuario`: nulo ate o V3.3, preenchido a partir do V3.4

O V3.3 nao tinha identidade, e o que tinha valor nao dependia dela: qual recorte,
quantas linhas, quando, qual formato. O V3.4 trouxe login e passou a preencher
`usuario` -- e nada mais mudou de forma, como estava previsto. A coluna segue
nulavel: registro antigo continua sem ator, e nao inventamos `'anonimo'`, que
faria "antes do login" e "usuario apagado" virarem a mesma coisa.

Registro de login **nao tem** recorte, formato nem linhas -- nao ha o que
preencher, e coluna nula aqui significa "nao se aplica a este evento".
"""

import json
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)

EVENTOS = ("download", "login")


def _conexao():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def abrir(evento, recorte=None, formato=None, ip=None, usuario=None) -> int:
    """Registra a tentativa e devolve o id. Commita na hora."""
    if evento not in EVENTOS:
        raise ValueError(f"evento fora do escopo da auditoria: {evento!r}")
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cat_auditoria
                    (evento, usuario, recorte, formato, ip, status)
                VALUES (%s, %s, %s, %s, %s, 'rodando')
                RETURNING id
                """,
                (
                    evento, usuario,
                    json.dumps(recorte or {}, ensure_ascii=False, default=str),
                    formato, ip,
                ),
            )
            registro = cur.fetchone()[0]
        conn.commit()
        return registro
    finally:
        conn.close()


def fechar(registro, linhas=None) -> None:
    """Conclui o registro com a contagem de linhas que realmente sairam."""
    _atualizar(registro, "ok", linhas=linhas)


def falhar(registro, erro) -> None:
    """Marca a tentativa como falha. Download interrompido nao pode aparecer
    como concluido."""
    _atualizar(registro, "erro", erro=str(erro)[:2000])
    logger.warning("auditoria %s: tentativa falhou -- %s", registro, erro)


def registrar_login(usuario, ip=None, ok=True, motivo=None) -> int:
    """Grava a tentativa de login **ja fechada** (V3.4).

    Download tem duas fases (`abrir` -> `fechar`/`falhar`) porque e um stream que
    pode morrer no meio. Login nao tem meio: ou a credencial confere, ou nao.
    Duas escritas para isso seriam duas idas ao banco em cada tentativa,
    inclusive nas erradas -- que sao justamente as que podem vir em rajada.

    **Sucesso e falha, os dois.** "Quem tentou entrar e nao conseguiu" e o que
    uma auditoria de acesso serve para responder. A senha nunca entra aqui: o que
    se guarda e o login tentado e o motivo da recusa."""
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cat_auditoria
                    (evento, usuario, ip, status, erro, terminado_em)
                VALUES ('login', %s, %s, %s, %s, now())
                RETURNING id
                """,
                (usuario, ip, "ok" if ok else "erro", motivo),
            )
            registro = cur.fetchone()[0]
        conn.commit()
        return registro
    finally:
        conn.close()


def _atualizar(registro, status, linhas=None, erro=None) -> None:
    conn = _conexao()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE cat_auditoria
                SET status = %s, terminado_em = now(), linhas = %s, erro = %s
                WHERE id = %s
                """,
                (status, linhas, erro, registro),
            )
        conn.commit()
    finally:
        conn.close()
