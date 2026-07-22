"""Motor de scores contra o Postgres real: estados, limiar e recalculo
idempotente. Comportamento fixado no Lote 3 (media/desvio amostral, janela 24,
minimo 6, |z| >= 2)."""

from datetime import date

from backend import motor


def _semear_serie(cur, sigla: str, metrica: str, valores: list[float], inicio=(2025, 1)):
    cur.execute("SELECT id FROM armazens WHERE sigla = %s", (sigla,))
    armazem_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM metricas WHERE nome = %s", (metrica,))
    metrica_id = cur.fetchone()[0]
    ano, mes = inicio
    for valor in valores:
        cur.execute(
            "INSERT INTO medidas (metrica_id, armazem_id, competencia, valor) VALUES (%s, %s, %s, %s)",
            (metrica_id, armazem_id, date(ano, mes, 1), valor),
        )
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return metrica_id, armazem_id


def _estados(cur, metrica_id, armazem_id) -> list[tuple]:
    cur.execute(
        """
        SELECT competencia, estado, z_score
        FROM scores
        WHERE metrica_id = %s AND armazem_id = %s
        ORDER BY competencia
        """,
        (metrica_id, armazem_id),
    )
    return cur.fetchall()


def test_historico_curto_normal_e_fora_padrao(cursor):
    # 6 meses com ruido leve, 6 meses na media (z=0) e salto forte no 13o —
    # o meio precisa ficar bem abaixo de |z|=2 contra o proprio historico
    serie = [100, 102, 98, 101, 99, 100, 100, 100, 100, 100, 100, 100, 200]
    metrica_id, armazem_id = _semear_serie(cursor, "RPI", "volumetria", serie)

    gravados = motor.calcular_scores(cursor)
    assert gravados == len(serie)

    estados = _estados(cursor, metrica_id, armazem_id)
    # 6 primeiros: sem historico minimo
    assert [e for _, e, _ in estados[:6]] == ["historico_curto"] * 6
    # do 7o ao 12o: dentro do padrao
    assert [e for _, e, _ in estados[6:12]] == ["normal"] * 6
    # 13o: salto -> fora do padrao com |z| >= 2
    competencia, estado, z = estados[12]
    assert (competencia, estado) == (date(2026, 1, 1), "fora_padrao")
    assert abs(float(z)) >= motor.LIMIAR_Z


def test_desvio_zero(cursor):
    # 6 meses identicos + 1 igual (normal) e depois 1 diferente (fora, z indefinido)
    metrica_id, armazem_id = _semear_serie(
        cursor, "MGG", "perdas", [50, 50, 50, 50, 50, 50, 50, 60]
    )
    motor.calcular_scores(cursor)
    estados = _estados(cursor, metrica_id, armazem_id)

    competencia, estado, z = estados[6]  # valor 50, media 50, desvio 0
    assert (estado, float(z)) == ("normal", 0.0)
    competencia, estado, z = estados[7]  # valor 60 != media, desvio 0
    assert (estado, z) == ("fora_padrao", None)


def test_recalculo_idempotente(cursor):
    _semear_serie(cursor, "RPI", "volumetria", [10, 11, 9, 10, 12, 10, 11, 30])

    motor.calcular_scores(cursor)
    cursor.execute(
        "SELECT metrica_id, armazem_id, competencia, media, desvio_padrao, z_score, estado "
        "FROM scores ORDER BY metrica_id, armazem_id, competencia"
    )
    primeira = cursor.fetchall()

    motor.calcular_scores(cursor)  # recalculo completo (delete+insert)
    cursor.execute(
        "SELECT metrica_id, armazem_id, competencia, media, desvio_padrao, z_score, estado "
        "FROM scores ORDER BY metrica_id, armazem_id, competencia"
    )
    segunda = cursor.fetchall()

    assert primeira == segunda
