"""Hash de senha: `hashlib.scrypt`, da biblioteca padrao.

## Por que scrypt, e nao uma dependencia nova

O `requirements.txt` **nao tem** bcrypt, passlib nem argon2, e trazer um deles
para dois papeis num app interno adicionaria dependencia binaria ao build da
imagem por um ganho que o scrypt ja entrega. `hashlib.scrypt` e stdlib e e
**memory-hard**: aumentar o custo de quebra exige memoria, nao so CPU, que e
justamente o que derruba ataque em GPU.

O que nao serve, e por que:

  - **SHA-256 cru** -- rapido de proposito. Bilhoes de tentativas por segundo.
  - **`hmac.compare_digest(senha, SENHA_DO_ENV)`** (o que a V2 faz) -- compara
    senha em claro; funciona para *uma* senha compartilhada, e nao ha o que
    guardar. Com identidade por pessoa existe hash guardado, e guardar senha
    reversivel de varias pessoas e uma classe de incidente inteira.
  - **PBKDF2** -- aceitavel, mas so CPU-hard.

Custo medido nesta maquina em 24/ago/2026: **~51 ms** por hash em n=2^14. E
caro o suficiente para forca bruta e imperceptivel num login.

## O formato guarda os parametros

    scrypt$16384$8$1$<sal em base64>$<hash em base64>

Os parametros vao **dentro** do valor guardado, e nao numa constante do modulo.
Sem isso, subir `N` no futuro invalidaria toda senha ja cadastrada -- ninguem
conseguiria entrar, porque a verificacao usaria um custo diferente do da
gravacao. Com o formato auto-descrito, hash antigo continua conferindo com o
custo antigo e hash novo nasce com o custo novo.

## Sal por senha

Sal aleatorio de 16 bytes por senha. Duas pessoas com a mesma senha produzem
hashes diferentes -- e o teste fixa isso. Sem sal, um hash igual ao outro
denunciaria "estas duas usam a mesma senha", e uma tabela pre-computada serviria
para todo mundo de uma vez.
"""

import base64
import hashlib
import hmac
import secrets

# n=2^14, r=8, p=1: ~51 ms e ~16 MB de memoria por verificacao nesta maquina.
# Estes valores valem para senha NOVA -- senha ja gravada e verificada com os
# parametros que estao no proprio valor guardado. Ver docstring.
N = 2**14
R = 8
P = 1
SAL_BYTES = 16
CHAVE_BYTES = 32

# 16 MB de buffer (128 * N * r) mais folga. Explicito para nao depender do
# padrao do OpenSSL, que varia entre builds e ja quebrou codigo alheio quando
# o default era menor do que o N pedido.
MAXMEM = 64 * 1024 * 1024

ALGORITMO = "scrypt"


def _b64(bruto: bytes) -> str:
    return base64.b64encode(bruto).decode("ascii")


def _derivar(senha: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"), salt=sal, n=n, r=r, p=p,
        dklen=CHAVE_BYTES, maxmem=MAXMEM,
    )


def gerar(senha: str) -> str:
    """Hash da senha, com sal novo e os parametros embutidos."""
    if not senha or not senha.strip():
        raise ValueError("senha vazia")
    sal = secrets.token_bytes(SAL_BYTES)
    chave = _derivar(senha, sal, N, R, P)
    return f"{ALGORITMO}${N}${R}${P}${_b64(sal)}${_b64(chave)}"


def confere(senha: str, guardado) -> bool:
    """Verdadeiro se a senha corresponde ao hash guardado.

    `guardado` nulo ou vazio devolve **falso**, nao erro: e o usuario de AD, que
    tem papel e nao tem senha local (ver a migration 0022). Ele nao entra por
    aqui, e isso e o comportamento correto -- nao uma excecao a tratar.

    Hash em formato desconhecido tambem devolve falso, e nao explode: uma linha
    corrompida em `cat_usuarios` nao deve derrubar o endpoint de login de todo
    mundo."""
    if not senha or not guardado:
        return False
    partes = str(guardado).split("$")
    if len(partes) != 6 or partes[0] != ALGORITMO:
        return False
    try:
        n, r, p = int(partes[1]), int(partes[2]), int(partes[3])
        sal = base64.b64decode(partes[4])
        esperado = base64.b64decode(partes[5])
    except (ValueError, TypeError):
        return False
    try:
        calculado = _derivar(senha, sal, n, r, p)
    except ValueError:
        # parametros absurdos guardados na linha (n nao potencia de 2, memoria
        # acima do teto). Falso e a resposta segura.
        return False
    return hmac.compare_digest(calculado, esperado)
