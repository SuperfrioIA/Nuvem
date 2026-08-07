"""Cache de consulta com TTL curto (lote V2.7).

Sem banco: o cache e um dicionario com TTL, e o que precisa ser provado e o
contrato dele -- acerto, expiracao, invalidacao, teto, e as duas recusas
(nao cacheia erro, nao confunde chaves parecidas).
"""

import pytest

from backend.services import cache_consulta


@pytest.fixture(autouse=True)
def cache_limpo():
    cache_consulta.invalidar("teste")
    yield
    cache_consulta.invalidar("teste")


def _contador():
    """Funcao de calculo que conta quantas vezes foi chamada de verdade."""
    chamadas = {"n": 0}

    def calcular():
        chamadas["n"] += 1
        return {"valor": chamadas["n"]}

    return chamadas, calcular


def test_segunda_chamada_com_os_mesmos_parametros_nao_recalcula():
    chamadas, calcular = _contador()
    primeira = cache_consulta.obter_ou_calcular("x", {"de": "2026-01"}, calcular, ttl=60)
    segunda = cache_consulta.obter_ou_calcular("x", {"de": "2026-01"}, calcular, ttl=60)

    assert primeira == segunda == {"valor": 1}
    assert chamadas["n"] == 1


def test_ordem_das_chaves_do_dicionario_nao_muda_a_chave_do_cache():
    """`sort_keys` na serializacao: sem isso o cache nunca acertaria, porque a
    ordem de insercao dos filtros varia entre endpoints."""
    chamadas, calcular = _contador()
    cache_consulta.obter_ou_calcular("x", {"de": "2026-01", "ate": "2026-07"}, calcular, ttl=60)
    cache_consulta.obter_ou_calcular("x", {"ate": "2026-07", "de": "2026-01"}, calcular, ttl=60)
    assert chamadas["n"] == 1


def test_parametro_diferente_e_consulta_diferente():
    chamadas, calcular = _contador()
    cache_consulta.obter_ou_calcular("x", {"filial": "RMSPII"}, calcular, ttl=60)
    cache_consulta.obter_ou_calcular("x", {"filial": "RMSPIII"}, calcular, ttl=60)
    cache_consulta.obter_ou_calcular("y", {"filial": "RMSPII"}, calcular, ttl=60)
    assert chamadas["n"] == 3


def test_none_e_ausente_nao_colidem():
    """`{"cliente": None}` e `{}` significam a mesma coisa no endpoint, mas o
    cache trata como chaves distintas -- o que custa um recalculo, nunca uma
    resposta errada. Este teste fixa que a distincao e a segura (nao acerta),
    nao a perigosa (acerta com o payload do outro)."""
    chamadas, calcular = _contador()
    cache_consulta.obter_ou_calcular("x", {"cliente": None}, calcular, ttl=60)
    cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=60)
    assert chamadas["n"] == 2


def test_ttl_expirado_recalcula():
    chamadas, calcular = _contador()
    cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=0.01)
    import time

    time.sleep(0.05)
    segunda = cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=0.01)
    assert chamadas["n"] == 2
    assert segunda == {"valor": 2}


def test_ttl_zero_desliga_o_cache_sem_tirar_o_caminho_do_codigo():
    chamadas, calcular = _contador()
    for _ in range(3):
        cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=0)
    assert chamadas["n"] == 3
    assert cache_consulta.estatisticas()["entradas"] == 0


def test_invalidar_descarta_tudo():
    chamadas, calcular = _contador()
    cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=60)
    quantas = cache_consulta.invalidar("processamento")
    cache_consulta.obter_ou_calcular("x", {}, calcular, ttl=60)

    assert quantas == 1
    assert chamadas["n"] == 2


def test_erro_nao_e_cacheado():
    """Consulta que falhou nao pode virar resposta cacheada -- a proxima
    tentativa tem que chegar ao banco de novo."""
    chamadas = {"n": 0}

    def falhar():
        chamadas["n"] += 1
        raise ValueError("filial desconhecida")

    for _ in range(2):
        with pytest.raises(ValueError):
            cache_consulta.obter_ou_calcular("x", {}, falhar, ttl=60)
    assert chamadas["n"] == 2
    assert cache_consulta.estatisticas()["entradas"] == 0


def test_teto_de_entradas_nao_deixa_o_cache_crescer_sem_limite(monkeypatch):
    """A chave inclui os filtros, que sao produto cartesiano -- sem teto o
    dicionario cresceria indefinidamente com quem brinca nos filtros."""
    monkeypatch.setattr(cache_consulta, "TETO_ENTRADAS", 5)
    _, calcular = _contador()
    for i in range(30):
        cache_consulta.obter_ou_calcular("x", {"i": i}, calcular, ttl=60)
    assert cache_consulta.estatisticas()["entradas"] <= 5
