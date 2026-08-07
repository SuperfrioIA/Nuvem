"""Cache de consulta com TTL curto, para as leituras do Cockpit (lote V2.7).

Motivo: uma carga do Cockpit dispara 8 requests, e as consultas de volumetria
agregam `medidas` varias vezes cada (`evolucao` chama `serie()` duas vezes,
`resumo` chama `evolucao` tres). Reapertar o F5 repete tudo. O cache tira o
trabalho repetido do banco -- e, por acerto, tira tambem a conexao do pool: o
`get_conn()` fica DENTRO da funcao que calcula, entao acerto de cache nao pega
conexao nenhuma.

Garantia declarada, e ela e uma so: **uma leitura pode estar desatualizada no
maximo `ttl` segundos** (60 por padrao, `CACHE_CONSULTA_TTL`). Nao existe
"cache coerente" aqui, e essa e a escolha: coerencia exigiria transacao ou
invalidacao distribuida, e o custo nao se paga numa ferramenta interna onde a
fonte e reprocessada algumas vezes por dia.

Invalidacao explicita (`invalidar()`) existe para o caminho que a pessoa VE
acontecer: processar o DataHub, criar/apagar de-para, processar upload manual e
reprocessar execucao. Sem ela, o admin que acabou de cadastrar um de-para
continuaria vendo a pendencia por um minuto e concluiria que o cadastro nao
funcionou.

Pendencia de CLIENTE e de TIPO DE ESTOQUE nao tem endpoint de resolucao (nao
existe cadastro de cliente pela API -- `/admin/clientes` e somente leitura):
elas saem do painel no proximo processamento, que invalida. Uma versao anterior
deste docstring citava "cadastrar cliente" entre os caminhos invalidados --
achado da revisao independente, era mencao a um endpoint que nao existe.

**Limite conhecido:** `scripts/processar_saida.py` roda em OUTRO processo
(decisao D4 do V2.3), então nao consegue chamar `invalidar()` daqui -- depois
dele a tela pode ficar ate `ttl` segundos mostrando o numero anterior. E o
mesmo bound de sempre, so vale saber que ali ele e o unico mecanismo.

Nao guarda erro: excecao propaga e nada e gravado -- consulta que falhou nao
pode virar resposta cacheada.

O valor guardado e o proprio dict devolvido pelo servico, sem copia. Quem
consome (os routers) so serializa; **nao mutar o dict devolvido**, ou a mutacao
aparece na proxima resposta.
"""

import json
import logging
import os
import threading
import time

logger = logging.getLogger("nuvem.cache")

TTL_PADRAO = float(os.environ.get("CACHE_CONSULTA_TTL", "60"))
# teto de entradas: a chave inclui os filtros, que sao um produto cartesiano
# (periodo x filial x cliente x tipo x grandeza x direcao x pagina) -- sem teto
# o dicionario cresceria indefinidamente com quem brinca nos filtros
TETO_ENTRADAS = int(os.environ.get("CACHE_CONSULTA_TETO", "256"))

_lock = threading.Lock()
_entradas: dict[str, tuple[float, object]] = {}
_estatisticas = {"acertos": 0, "faltas": 0, "invalidacoes": 0, "expulsoes": 0}


def _chave(nome: str, parametros: dict) -> str:
    """Chave determinística. `sort_keys` importa: dois dicts iguais com ordem de
    insercao diferente tem que dar a MESMA chave, senao o cache nunca acerta."""
    return nome + "|" + json.dumps(parametros, sort_keys=True, default=str, ensure_ascii=False)


def _expulsar_se_preciso(agora: float) -> None:
    """Chamado com o lock tomado. Tira primeiro o que ja expirou; se ainda
    estourar o teto, tira o de expiracao mais proxima (o mais velho)."""
    if len(_entradas) < TETO_ENTRADAS:
        return
    for chave in [c for c, (expira, _) in _entradas.items() if expira <= agora]:
        del _entradas[chave]
        _estatisticas["expulsoes"] += 1
    while len(_entradas) >= TETO_ENTRADAS:
        mais_velha = min(_entradas, key=lambda c: _entradas[c][0])
        del _entradas[mais_velha]
        _estatisticas["expulsoes"] += 1


def obter_ou_calcular(nome: str, parametros: dict, calcular, ttl: float | None = None):
    """Devolve o valor cacheado de (nome, parametros) ou chama `calcular()`.

    `calcular` e uma funcao sem argumentos -- e ela que abre a conexao com o
    banco, entao acerto de cache nao consome conexao do pool.

    `ttl=0` (ou negativo) desliga o cache para aquela chamada, sem tirar o
    caminho do codigo: e o que os testes usam pra provar que a consulta por
    baixo continua correta.
    """
    ttl_efetivo = TTL_PADRAO if ttl is None else ttl
    if ttl_efetivo <= 0:
        return calcular()

    chave = _chave(nome, parametros)
    agora = time.monotonic()
    with _lock:
        guardado = _entradas.get(chave)
        if guardado and guardado[0] > agora:
            _estatisticas["acertos"] += 1
            return guardado[1]
        _estatisticas["faltas"] += 1

    # calcula FORA do lock: consulta lenta nao pode bloquear os outros requests
    # (o preco e duas requisicoes simultaneas da mesma chave calcularem as duas
    # -- desperdicio aceitavel; o contrario seria serializar a tela inteira)
    valor = calcular()

    with _lock:
        _expulsar_se_preciso(time.monotonic())
        _entradas[chave] = (time.monotonic() + ttl_efetivo, valor)
    return valor


def invalidar(motivo: str = "") -> int:
    """Descarta tudo. Chamado pelas escritas que a pessoa acabou de fazer
    (processar o DataHub, criar/apagar de-para, upload manual, reprocessamento de
    execucao) -- devolve quantas entradas caíram, pra quem quiser logar."""
    with _lock:
        quantas = len(_entradas)
        _entradas.clear()
        _estatisticas["invalidacoes"] += 1
    if quantas:
        logger.info("cache de consulta invalidado (%s): %s entrada(s)", motivo or "sem motivo", quantas)
    return quantas


def estatisticas() -> dict:
    with _lock:
        return {**_estatisticas, "entradas": len(_entradas), "ttl_segundos": TTL_PADRAO}
