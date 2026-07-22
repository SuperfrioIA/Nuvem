"""Ingestao (gravar_agregados) contra o Postgres real: de-para, pendencia e
idempotencia do upsert."""

from datetime import date

from backend import ingestao
from tests.conftest import consultar


def _conector_id(cur) -> int:
    cur.execute("SELECT id FROM conectores WHERE tipo = 'upload_manual'")
    return cur.fetchone()[0]


def test_depara_resolve_e_pendencia(cursor):
    conector_id = _conector_id(cursor)
    agregados = [
        # "RMSPIII" e "46" resolvem pro mesmo armazem pelo seed do Lote 7/8
        {"armazem_na_fonte": "RMSPIII", "competencia": date(2026, 7, 1),
         "metrica": "posicoes_ocupadas", "valor": 9773},
        {"armazem_na_fonte": "46", "competencia": date(2026, 7, 1),
         "metrica": "comercial_vigente", "valor": 9773},
        # sigla desconhecida: NAO grava e NAO some em silencio — vira pendencia
        {"armazem_na_fonte": "XPTO", "competencia": date(2026, 7, 1),
         "metrica": "posicoes_ocupadas", "valor": 1},
    ]

    gravadas = ingestao.gravar_agregados(cursor, conector_id, agregados)
    assert gravadas == 2

    cursor.execute(
        """
        SELECT a.sigla, m.nome, md.valor
        FROM medidas md
        JOIN armazens a ON a.id = md.armazem_id
        JOIN metricas m ON m.id = md.metrica_id
        ORDER BY m.nome
        """
    )
    linhas = cursor.fetchall()
    assert [(s, n, float(v)) for s, n, v in linhas] == [
        ("RMSPIII", "comercial_vigente", 9773.0),
        ("RMSPIII", "posicoes_ocupadas", 9773.0),
    ]

    cursor.execute("SELECT armazem_na_fonte FROM depara_pendencias")
    assert cursor.fetchall() == [("XPTO",)]


def test_upsert_idempotente_e_corrige_valor(cursor):
    conector_id = _conector_id(cursor)
    item = {"armazem_na_fonte": "RPI", "competencia": date(2026, 6, 1),
            "metrica": "volumetria_recebimento", "valor": 100.0}

    ingestao.gravar_agregados(cursor, conector_id, [item])
    ingestao.gravar_agregados(cursor, conector_id, [item])  # 2x nao duplica

    cursor.execute("SELECT count(*), min(valor) FROM medidas")
    total, valor = cursor.fetchone()
    assert (total, float(valor)) == (1, 100.0)

    # nova carga com valor corrigido: upsert substitui, nao acumula
    ingestao.gravar_agregados(cursor, conector_id, [dict(item, valor=120.0)])
    cursor.execute("SELECT count(*), min(valor) FROM medidas")
    total, valor = cursor.fetchone()
    assert (total, float(valor)) == (1, 120.0)


def test_seeds_idempotentes(banco_migrado):
    """Rodar init_db de novo (como acontece a cada restart) nao duplica nada."""
    from backend.database import init_db

    antes = {
        tabela: consultar(f"SELECT count(*) FROM {tabela}")[0][0]
        for tabela in ("armazens", "depara_armazem", "metricas", "clientes",
                       "catalogo_fontes", "catalogo_colunas", "conectores")
    }
    init_db()
    depois = {
        tabela: consultar(f"SELECT count(*) FROM {tabela}")[0][0]
        for tabela in antes
    }
    assert antes == depois
    # sanidade do seed: 34 armazens (32 ativos + MRS e RMSPIV inativas)
    assert antes["armazens"] == 34
    assert consultar("SELECT count(*) FROM armazens WHERE ativo")[0][0] == 32
