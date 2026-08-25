"""Quem a pessoa e: autenticacao e freio de tentativas.

## O modulo que o AD vai substituir

Este e o **unico** lugar que sabe *como* se prova identidade. Hoje: senha local
em `cat_usuarios`. No dia do AD, `autenticar()` passa a consultar o diretorio e
o resto do sistema nao muda -- porque papel, `ativo`, sessao e auditoria nunca
perguntaram como a senha foi conferida.

E por isso que `autenticar()` devolve um `Usuario` do **nosso** banco, e nao um
objeto do provedor: o AD dira "esta pessoa e quem diz ser"; quem ela e *aqui*
continua sendo a linha de `cat_usuarios`. Pessoa autenticada no AD sem linha
nossa nao entra -- e isso e proposital, senao o dominio inteiro da SuperFrio
teria acesso a volumetria de catering no dia da virada.

## Sem FastAPI aqui

Este modulo levanta `MuitasTentativas`, nao `HTTPException`. O mapeamento para
429 e trabalho do `app.py`. Assim a politica de freio e testavel sem subir HTTP,
e o dia em que existir um segundo caminho de login (CLI, script) ele herda o
mesmo freio sem herdar o framework.

## Freio por login E por IP

A V2 freava **so por IP**, e o comentario dela explica por que: senha unica, sem
identidade por pessoa, o IP era a unica chave disponivel. Isso tem um custo que
a propria V2 registrou -- o CSC atras do mesmo IP da rede da SuperFrio trava
inteiro quando uma pessoa erra a senha varias vezes.

Com identidade por pessoa a chave certa passa a ser o **login**: quem erra trava
a si mesmo, e o colega ao lado continua trabalhando. O freio por IP fica, mais
frouxo, para o caso que o freio por login nao pega: varredura de logins
diferentes a partir da mesma origem.

  - por login: 5 falhas em 10 min -> 10 min de bloqueio;
  - por IP: 30 falhas em 10 min -> 10 min de bloqueio.

Em memoria, de proposito, como na V2: perde o estado num restart do container.
E proporcional a uma ferramenta interna -- nao e defesa contra atacante
determinado, e sim contra tentativa e erro. Persistir isso exigiria uma tabela
escrita a cada falha, e a auditoria ja guarda o que interessa depois.

## Tempo igual para usuario que existe e usuario que nao existe

Login inexistente tambem paga um scrypt (em um hash descartavel). Sem isso, a
resposta voltaria em ~0 ms para login inexistente e ~51 ms para login existente
com senha errada -- e essa diferenca e um oraculo: da para descobrir **quem tem
conta** sem acertar senha nenhuma.
"""

import logging
import time

from catering.seguranca import senha as mod_senha
from catering.seguranca import usuarios

logger = logging.getLogger(__name__)

FALHAS_POR_LOGIN = 5
FALHAS_POR_IP = 30
JANELA_SEGUNDOS = 10 * 60
BLOQUEIO_SEGUNDOS = 10 * 60

_falhas: dict[str, list[float]] = {}
_bloqueado_ate: dict[str, float] = {}

# hash descartavel, so para igualar o tempo de resposta -- ver docstring
_HASH_ISCA = None


class MuitasTentativas(Exception):
    """Freio de tentativas ativo. O `app.py` traduz para 429."""

    def __init__(self, segundos):
        self.segundos = max(1, int(segundos))
        super().__init__(
            f"muitas tentativas -- tente novamente em {self.segundos // 60 + 1} min"
        )


def _isca() -> str:
    global _HASH_ISCA
    if _HASH_ISCA is None:
        _HASH_ISCA = mod_senha.gerar("nao-e-senha-de-ninguem")
    return _HASH_ISCA


def _chaves(login, ip):
    """As duas chaves de freio. `None` no IP e ignorado, nao virado em string --
    freio por "desconhecido" juntaria origens diferentes num mesmo balde."""
    chaves = [f"login:{usuarios.normalizar(login)}"]
    if ip:
        chaves.append(f"ip:{ip}")
    return chaves


def _teto(chave) -> int:
    return FALHAS_POR_LOGIN if chave.startswith("login:") else FALHAS_POR_IP


def verificar_freio(login, ip=None) -> None:
    """Levanta `MuitasTentativas` se login ou IP estiverem bloqueados."""
    agora = time.time()
    for chave in _chaves(login, ip):
        ate = _bloqueado_ate.get(chave)
        if ate is not None:
            if agora < ate:
                raise MuitasTentativas(ate - agora)
            _bloqueado_ate.pop(chave, None)


def registrar_falha(login, ip=None) -> None:
    agora = time.time()
    for chave in _chaves(login, ip):
        tentativas = [
            t for t in _falhas.get(chave, []) if agora - t < JANELA_SEGUNDOS
        ]
        tentativas.append(agora)
        _falhas[chave] = tentativas
        if len(tentativas) >= _teto(chave):
            _bloqueado_ate[chave] = agora + BLOQUEIO_SEGUNDOS
            logger.warning(
                "freio de login ativado para %s (%d falhas)", chave, len(tentativas)
            )


def registrar_sucesso(login, ip=None) -> None:
    """Zera o contador do login. **Nao zera o do IP**: uma varredura que acerta
    uma conta no meio nao deve limpar o rastro das outras tentativas."""
    chave = f"login:{usuarios.normalizar(login)}"
    _falhas.pop(chave, None)
    _bloqueado_ate.pop(chave, None)


def zerar_freio() -> None:
    """So para teste e para o CLI. Estado em memoria, ver docstring."""
    _falhas.clear()
    _bloqueado_ate.clear()


def autenticar(login, senha):
    """`Usuario` se a credencial confere e a conta esta ativa; `None` se nao.

    Devolve `None` -- sem dizer qual dos motivos -- de proposito: "senha errada"
    e "esse login nao existe" sao a mesma resposta para quem esta tentando
    adivinhar. O motivo real vai para o log e para a auditoria, que sao nossos.

    Nao aplica o freio: quem chama decide (o `app.py` verifica antes e registra
    a falha depois), porque o freio depende do IP, que e um fato de HTTP."""
    login = usuarios.normalizar(login)
    usuario, hash_guardado = usuarios.buscar_para_autenticar(login)

    if usuario is None:
        # paga o mesmo custo de um login existente -- ver docstring
        mod_senha.confere(senha or "", _isca())
        logger.info("login recusado: %s (nao existe)", login)
        return None

    if not usuario.ativo:
        mod_senha.confere(senha or "", _isca())
        logger.info("login recusado: %s (inativo)", login)
        return None

    if not mod_senha.confere(senha or "", hash_guardado):
        # inclui o caso do usuario de AD: papel sim, senha local nao. Ele nao
        # entra por aqui hoje, e isso e o comportamento correto.
        motivo = "sem senha local" if not hash_guardado else "senha incorreta"
        logger.info("login recusado: %s (%s)", login, motivo)
        return None

    usuarios.marcar_acesso(login)
    return usuario
