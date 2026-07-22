"""Lote R1 — fontes logicas + versionamento real dos modelos de importacao.

Cobre, com Postgres real (nada de mock):
- banco novo sobe com R0 + R1 (tabelas/colunas novas presentes);
- modelos existentes viram versao v1 na migration (banco legado);
- execucao antiga com modelo ganha a v1; sem modelo fica NULL;
- o hash gravado pela migration bate com backend/versoes (algoritmo unico);
- upload novo grava modelo_versao_id (a versao exata usada);
- upload novo usa a versao ativa/padrao; reprocessamento usa a versao ORIGINAL;
- versao nova nao altera a v1 nem a execucao antiga;
- versao inativa nao e usada como padrao (logica + CHECK no banco).

Os arquivos sao sinteticos (tests/arquivos_sinteticos.py) — provam a mecanica,
nao a qualidade do dado real.
"""

import copy
import json
import os

import psycopg2
import psycopg2.errors
import pytest
from alembic import command

from backend import migracao, versoes
from tests import arquivos_sinteticos, modelos_reais
from tests.conftest import consultar

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload_novo(cliente, chave: str):
    """Upload que cria um modelo novo (nome + mapeamento reais da fonte)."""
    nome_arquivo, gerador = arquivos_sinteticos.ARQUIVOS[chave]
    mime = XLSX_MIME if nome_arquivo.endswith(".xlsx") else "text/csv"
    return cliente.post(
        "/api/admin/upload/processar",
        files={"arquivo": (nome_arquivo, gerador(), mime)},
        data={"nome_novo_modelo": chave, "mapeamento_json": json.dumps(modelos_reais.TODOS[chave])},
    )


def _upload_com_modelo(cliente, chave: str, modelo_id: int):
    nome_arquivo, gerador = arquivos_sinteticos.ARQUIVOS[chave]
    mime = XLSX_MIME if nome_arquivo.endswith(".xlsx") else "text/csv"
    return cliente.post(
        "/api/admin/upload/processar",
        files={"arquivo": (nome_arquivo, gerador(), mime)},
        data={"modelo_id": str(modelo_id)},
    )


def _volumetria_recebimento_rmspii_jun() -> float | None:
    linhas = consultar(
        """
        SELECT md.valor::float FROM medidas md
        JOIN armazens a ON a.id = md.armazem_id
        JOIN metricas m ON m.id = md.metrica_id
        WHERE a.sigla = 'RMSPII' AND m.nome = 'volumetria_recebimento'
          AND md.competencia = DATE '2026-06-01'
        """
    )
    return linhas[0][0] if linhas else None


# --------------------------------------------------------------------------
# schema (banco novo com R0 + R1)
# --------------------------------------------------------------------------

def test_banco_novo_tem_r0_e_r1(banco_migrado):
    tabelas = {t for (t,) in consultar(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )}
    assert "modelo_versoes" in tabelas                       # R1
    assert {"medidas", "execucoes", "modelos_importacao"} <= tabelas  # R0

    colunas_exec = {c for (c,) in consultar(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='execucoes'"
    )}
    assert "modelo_versao_id" in colunas_exec

    colunas_modelo = {c for (c,) in consultar(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='modelos_importacao'"
    )}
    assert "fonte_id" in colunas_modelo

    colunas_fonte = {c for (c,) in consultar(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='catalogo_fontes'"
    )}
    assert "ativo" in colunas_fonte


# --------------------------------------------------------------------------
# migration: modelos existentes -> v1; execucoes antigas -> v1 quando possivel
# --------------------------------------------------------------------------

def test_migracao_converte_modelos_existentes_em_v1(banco_vazio):
    cfg = migracao._config()
    # 1) banco no estado R0 (so a baseline), com um modelo e execucoes gravados
    command.upgrade(cfg, migracao.BASELINE)

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("INSERT INTO conectores (tipo, nome) VALUES ('upload_manual','Upload') RETURNING id")
        conector_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO modelos_importacao (conector_id, nome, mapeamento) VALUES (%s,%s,%s) RETURNING id",
            (conector_id, "modelo-legado", json.dumps(modelos_reais.POS_SUM)),
        )
        modelo_id = cur.fetchone()[0]
        # execucao antiga COM modelo -> deve ganhar a v1
        cur.execute(
            "INSERT INTO execucoes (conector_id, modelo_id, origem, status) VALUES (%s,%s,'manual','ok') RETURNING id",
            (conector_id, modelo_id),
        )
        exec_com_modelo = cur.fetchone()[0]
        # execucao antiga SEM modelo -> fica NULL
        cur.execute(
            "INSERT INTO execucoes (conector_id, origem, status) VALUES (%s,'manual','ok') RETURNING id",
            (conector_id,),
        )
        exec_sem_modelo = cur.fetchone()[0]
    conn.close()

    # 2) sobe pro head (roda a 0002)
    command.upgrade(cfg, "head")

    versoes_do_modelo = consultar(
        "SELECT versao, ativo, padrao, hash_config, mapeamento FROM modelo_versoes WHERE modelo_id = %s",
        (modelo_id,),
    )
    assert len(versoes_do_modelo) == 1
    versao, ativo, padrao, hash_config, mapeamento = versoes_do_modelo[0]
    assert versao == 1 and ativo is True and padrao is True
    assert mapeamento == modelos_reais.POS_SUM
    # o hash da migration bate com o do runtime (algoritmo unico)
    assert hash_config == versoes.hash_mapeamento(modelos_reais.POS_SUM)

    # execucao com modelo aponta pra v1; sem modelo continua NULL
    v1_id = consultar("SELECT id FROM modelo_versoes WHERE modelo_id = %s", (modelo_id,))[0][0]
    assert consultar("SELECT modelo_versao_id FROM execucoes WHERE id = %s", (exec_com_modelo,)) == [(v1_id,)]
    assert consultar("SELECT modelo_versao_id FROM execucoes WHERE id = %s", (exec_sem_modelo,)) == [(None,)]


# --------------------------------------------------------------------------
# upload novo grava a versao exata
# --------------------------------------------------------------------------

def test_upload_novo_grava_modelo_versao_id(cliente):
    resposta = _upload_novo(cliente, "pos_sum")
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    modelo_versao_id = corpo["modelo_versao_id"]
    assert modelo_versao_id

    # a execucao gravou a versao usada
    assert consultar(
        "SELECT modelo_versao_id FROM execucoes WHERE id = %s", (corpo["execucao_id"],)
    ) == [(modelo_versao_id,)]

    # e essa versao e a v1 (ativa e padrao) do modelo criado
    v = consultar(
        "SELECT versao, ativo, padrao FROM modelo_versoes WHERE id = %s", (modelo_versao_id,)
    )
    assert v == [(1, True, True)]


# --------------------------------------------------------------------------
# reprocessamento usa a versao ORIGINAL; upload novo usa a padrao atual
# --------------------------------------------------------------------------

def test_reprocessamento_usa_versao_original(cliente):
    # v1: divisor 1000 -> recebimento RMSPII jun = 16000 t
    primeira = _upload_novo(cliente, "volumetria_fato")
    assert primeira.status_code == 200, primeira.text
    modelo_id = primeira.json()["modelo_id"]
    v1_id = primeira.json()["modelo_versao_id"]
    exec1 = primeira.json()["execucao_id"]
    assert _volumetria_recebimento_rmspii_jun() == 16000.0

    # v2: mesma fonte, divisor 2000 -> daria 8000 t (regra diferente)
    v2_map = copy.deepcopy(modelos_reais.VOLUMETRIA_FATO)
    for m in v2_map["metricas"]:
        m["divisor"] = 2000
    r_versao = cliente.post(
        f"/api/admin/modelos/{modelo_id}/versoes", data={"mapeamento_json": json.dumps(v2_map)}
    )
    assert r_versao.status_code == 200, r_versao.text
    assert r_versao.json()["versao"] == 2

    # reprocessar a execucao original: usa a v1 (16000), NAO a v2 (8000)
    reproc = cliente.post(f"/api/admin/execucoes/{exec1}/reprocessar")
    assert reproc.status_code == 200, reproc.text
    assert reproc.json()["modelo_versao_id"] == v1_id  # a versao original, nao a mais nova
    assert reproc.json()["execucao_id"] != exec1        # execucao nova, a antiga preservada
    assert _volumetria_recebimento_rmspii_jun() == 16000.0

    # upload novo com o modelo salvo: usa a versao ativa/padrao (v2) -> 8000
    novo = _upload_com_modelo(cliente, "volumetria_fato", modelo_id)
    assert novo.status_code == 200, novo.text
    assert novo.json()["modelo_versao_id"] != v1_id
    assert _volumetria_recebimento_rmspii_jun() == 8000.0


# --------------------------------------------------------------------------
# versao nova nao altera a v1 nem a execucao antiga
# --------------------------------------------------------------------------

def test_nova_versao_preserva_v1_e_execucao_antiga(cliente):
    primeira = _upload_novo(cliente, "capacidade_hdr")
    modelo_id = primeira.json()["modelo_id"]
    v1_id = primeira.json()["modelo_versao_id"]
    exec1 = primeira.json()["execucao_id"]

    antes = consultar(
        "SELECT versao, mapeamento, hash_config, ativo, padrao FROM modelo_versoes WHERE id = %s", (v1_id,)
    )[0]

    v2_map = copy.deepcopy(modelos_reais.CAPACIDADE_HDR)
    v2_map["competencia"] = {"tipo": "fixo", "valor": "2026-08"}
    cliente.post(f"/api/admin/modelos/{modelo_id}/versoes", data={"mapeamento_json": json.dumps(v2_map)})

    # a v1 nao mudou (mapeamento/hash iguais); so o padrao saiu dela
    depois = consultar(
        "SELECT versao, mapeamento, hash_config, ativo, padrao FROM modelo_versoes WHERE id = %s", (v1_id,)
    )[0]
    assert depois[:4] == antes[:4]      # versao, mapeamento, hash, ativo intactos
    assert antes[4] is True and depois[4] is False  # padrao migrou pra v2

    # a versao nova e a padrao agora
    padrao = consultar(
        "SELECT versao FROM modelo_versoes WHERE modelo_id = %s AND padrao", (modelo_id,)
    )
    assert padrao == [(2,)]

    # a execucao antiga continua apontando pra v1
    assert consultar("SELECT modelo_versao_id FROM execucoes WHERE id = %s", (exec1,)) == [(v1_id,)]


# --------------------------------------------------------------------------
# versao inativa nao e usada como padrao
# --------------------------------------------------------------------------

def test_versao_inativa_nao_e_padrao(banco_migrado):
    url = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM conectores WHERE tipo='upload_manual'")
        conector_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO modelos_importacao (conector_id, nome, mapeamento) VALUES (%s,'m-inativa','{}') RETURNING id",
            (conector_id,),
        )
        modelo_id = cur.fetchone()[0]
        # versao inativa e nao-padrao
        versoes.criar_versao(cur, modelo_id, {"a": 1}, padrao=False, ativo=False)
        # a resolucao de padrao ignora versao inativa
        assert versoes.resolver_versao_padrao(cur, modelo_id) is None
    conn.close()

    # o banco rejeita padrao=true com ativo=false (CHECK padrao_exige_ativo)
    conn2 = psycopg2.connect(url)
    try:
        with pytest.raises(psycopg2.errors.CheckViolation):
            with conn2.cursor() as cur:
                cur.execute(
                    "INSERT INTO modelo_versoes (modelo_id, versao, mapeamento, hash_config, ativo, padrao) "
                    "VALUES (%s, 2, '{}', 'x', false, true)",
                    (modelo_id,),
                )
    finally:
        conn2.rollback()
        conn2.close()


# --------------------------------------------------------------------------
# Lote R1.1 — seed dos modelos canonicos (fonte -> modelo -> versao v1)
# --------------------------------------------------------------------------

_FONTES_CANONICAS = {
    "ocupacao_fisica": "pos_sum",
    "capacidade": "capacidade_hdr",
    "ocupacao_comercial": "ocupacao_comercial",
    "ocupacao_manual": "ocupacao_manual",
    "volumetria": "volumetria_fato",
}


def test_banco_novo_liga_fonte_modelo_versao_v1(banco_migrado):
    """Banco novo ja nasce utilizavel: cada fonte logica canonica tem um modelo
    vinculado (nos dois sentidos) e uma v1 ativa/padrao — sem criacao manual."""
    ligacoes = consultar(
        """
        SELECT cf.chave, cf.ativo, mi.id
        FROM catalogo_fontes cf
        JOIN modelos_importacao mi ON mi.fonte_id = cf.id AND cf.modelo_id = mi.id
        """
    )
    assert {chave for chave, *_ in ligacoes} == set(_FONTES_CANONICAS)  # as 5, ligadas
    assert all(ativo for _chave, ativo, _mid in ligacoes)              # fontes ativas

    for _chave, _ativo, modelo_id in ligacoes:
        assert consultar(
            "SELECT versao, ativo, padrao FROM modelo_versoes WHERE modelo_id = %s", (modelo_id,)
        ) == [(1, True, True)]  # exatamente uma versao: v1 ativa e padrao

    # idempotente: rodar o seed de novo nao cria modelo nem versao a mais
    from backend.database import init_db

    init_db()
    assert consultar("SELECT count(*) FROM modelos_importacao WHERE fonte_id IS NOT NULL")[0][0] == 5
    assert consultar("SELECT count(*) FROM modelo_versoes")[0][0] == 5


def test_cinco_uploads_usam_a_versao_padrao_semeada(cliente):
    """Os 5 uploads da POC, feitos contra os modelos SEMEADOS (por modelo_id),
    usam a versao v1 ativa/padrao e produzem os numeros conferidos a mao."""
    for chave_fonte, chave_arquivo in _FONTES_CANONICAS.items():
        modelo_id = consultar(
            "SELECT mi.id FROM modelos_importacao mi "
            "JOIN catalogo_fontes cf ON cf.id = mi.fonte_id WHERE cf.chave = %s",
            (chave_fonte,),
        )[0][0]
        v1_id = consultar(
            "SELECT id FROM modelo_versoes WHERE modelo_id = %s AND padrao AND ativo", (modelo_id,)
        )[0][0]

        resp = _upload_com_modelo(cliente, chave_arquivo, modelo_id)
        assert resp.status_code == 200, resp.text
        assert resp.json()["modelo_versao_id"] == v1_id  # usou a v1 padrao semeada
        assert consultar(
            "SELECT modelo_versao_id FROM execucoes WHERE id = %s", (resp.json()["execucao_id"],)
        ) == [(v1_id,)]

    medidas = set(consultar(
        "SELECT a.sigla, m.nome, md.competencia::text, md.valor::float "
        "FROM medidas md JOIN armazens a ON a.id=md.armazem_id "
        "JOIN metricas m ON m.id=md.metrica_id"
    ))
    assert ("RMSPIII", "posicoes_ocupadas", "2026-07-01", 9773.0) in medidas
    assert ("RMSPII", "volumetria_recebimento", "2026-06-01", 16000.0) in medidas
    assert ("RMSP", "ocupacao_manual", "2026-07-01", 700.0) in medidas

    # os uploads usaram os modelos semeados, nao criaram novos
    assert consultar("SELECT count(*) FROM modelos_importacao")[0][0] == 5
