"""Ingestao (gravar_agregados) contra o Postgres real: de-para, pendencia e
idempotencia do upsert."""

from datetime import date

from backend import ingestao
from tests.conftest import consultar


def _conector_id(cur) -> int:
    cur.execute("SELECT id FROM conectores WHERE tipo = 'upload_manual'")
    return cur.fetchone()[0]


def _execucao(cur, conector_id: int, origem: str = "manual") -> int:
    return ingestao.iniciar_execucao(cur, conector_id, None, None, origem, None)


def test_depara_resolve_e_pendencia(cursor):
    conector_id = _conector_id(cursor)
    execucao_id = _execucao(cursor, conector_id)
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

    gravadas = ingestao.gravar_agregados(cursor, conector_id, execucao_id, agregados)
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

    execucao_id = _execucao(cursor, conector_id)
    ingestao.gravar_agregados(cursor, conector_id, execucao_id, [item])
    ingestao.gravar_agregados(cursor, conector_id, execucao_id, [item])  # 2x nao duplica

    cursor.execute("SELECT count(*), min(valor) FROM medidas")
    total, valor = cursor.fetchone()
    assert (total, float(valor)) == (1, 100.0)

    # nova carga com valor corrigido: upsert substitui, nao acumula
    ingestao.gravar_agregados(cursor, conector_id, execucao_id, [dict(item, valor=120.0)])
    cursor.execute("SELECT count(*), min(valor) FROM medidas")
    total, valor = cursor.fetchone()
    assert (total, float(valor)) == (1, 120.0)


def test_grava_recebida_e_publica_canonica_vinculada(cursor):
    conector_id = _conector_id(cursor)
    execucao_id = _execucao(cursor, conector_id)
    item = {"armazem_na_fonte": "RMSPIII", "competencia": date(2026, 7, 1),
            "metrica": "posicoes_ocupadas", "valor": 9773.0}

    ingestao.gravar_agregados(cursor, conector_id, execucao_id, [item])

    cursor.execute(
        "SELECT id, execucao_id, armazem_id, metrica_id, competencia, valor FROM medidas_recebidas"
    )
    recebida_id, exec_gravado, armazem_id, metrica_id, competencia, valor = cursor.fetchone()
    assert (exec_gravado, competencia, float(valor)) == (execucao_id, date(2026, 7, 1), 9773.0)

    cursor.execute(
        "SELECT origem_tipo, medida_recebida_id FROM medidas WHERE armazem_id = %s AND metrica_id = %s",
        (armazem_id, metrica_id),
    )
    assert cursor.fetchone() == ("recebida", recebida_id)


def test_recebida_acumula_por_execucao_canonica_permanece_idempotente(cursor):
    """Reprocesso = execucao nova: medidas_recebidas acumula (append-only),
    mas a canonica em medidas continua idempotente (upsert por celula)."""
    conector_id = _conector_id(cursor)
    item = {"armazem_na_fonte": "RPI", "competencia": date(2026, 6, 1),
            "metrica": "volumetria_recebimento", "valor": 100.0}

    exec1 = _execucao(cursor, conector_id, "manual")
    ingestao.gravar_agregados(cursor, conector_id, exec1, [item])

    exec2 = _execucao(cursor, conector_id, "reprocessamento")
    ingestao.gravar_agregados(cursor, conector_id, exec2, [dict(item, valor=120.0)])

    cursor.execute("SELECT count(*) FROM medidas_recebidas")
    assert cursor.fetchone()[0] == 2  # uma recebida por execucao, nenhuma sobrescrita

    cursor.execute("SELECT count(*), min(valor) FROM medidas")
    total, valor = cursor.fetchone()
    assert (total, float(valor)) == (1, 120.0)  # canonica segue com 1 linha por celula


def test_medida_derivada_registra_regra_e_linhagem(cursor):
    conector_id = _conector_id(cursor)
    execucao_id = _execucao(cursor, conector_id)
    item = {"armazem_na_fonte": "RPI", "competencia": date(2026, 6, 1),
            "metrica": "volumetria_recebimento", "valor": 10.0}
    ingestao.gravar_agregados(cursor, conector_id, execucao_id, [item])

    cursor.execute("SELECT id, armazem_id FROM medidas_recebidas")
    recebida_id, armazem_id = cursor.fetchone()

    metrica_derivada_id = ingestao.get_or_create_metrica(cursor, "metrica_derivada_teste")
    medida_id = ingestao.registrar_medida_derivada(
        cursor, metrica_derivada_id, armazem_id, date(2026, 6, 1), 55.0,
        regra_codigo="teste_r2", regra_versao="v1",
        origens=[("recebida", recebida_id, "parcela_teste")],
    )

    cursor.execute(
        "SELECT origem_tipo, regra_codigo, regra_versao, calculado_em IS NOT NULL FROM medidas WHERE id = %s",
        (medida_id,),
    )
    assert cursor.fetchone() == ("derivada", "teste_r2", "v1", True)

    cursor.execute(
        "SELECT medida_origem_tipo, medida_origem_id, papel_origem FROM medida_linhagem WHERE medida_id = %s",
        (medida_id,),
    )
    assert cursor.fetchall() == [("recebida", recebida_id, "parcela_teste")]


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
