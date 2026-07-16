"""Camada comum de gravacao: resolve de-para, garante metrica, grava medida.

Compartilhada por qualquer conector que produza o formato canonico
{armazem_na_fonte, competencia, metrica, valor} -- nao e especifica do
upload_manual.
"""


def get_or_create_metrica(cur, nome: str) -> int:
    cur.execute("SELECT id FROM metricas WHERE nome = %s", (nome,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO metricas (nome) VALUES (%s) RETURNING id", (nome,))
    return cur.fetchone()[0]


def resolver_armazem(cur, conector_id: int, armazem_na_fonte: str):
    cur.execute(
        "SELECT armazem_id FROM depara_armazem WHERE conector_id = %s AND armazem_na_fonte = %s",
        (conector_id, armazem_na_fonte),
    )
    row = cur.fetchone()
    return row[0] if row else None


def registrar_pendencia(cur, conector_id: int, armazem_na_fonte: str) -> None:
    cur.execute(
        """
        INSERT INTO depara_pendencias (conector_id, armazem_na_fonte)
        VALUES (%s, %s)
        ON CONFLICT (conector_id, armazem_na_fonte)
        DO UPDATE SET ultima_vez_em = now()
        """,
        (conector_id, armazem_na_fonte),
    )


def upsert_medida(cur, metrica_id: int, armazem_id: int, competencia, valor: float, conector_id: int) -> None:
    cur.execute(
        """
        INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, conector_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (metrica_id, armazem_id, competencia)
        DO UPDATE SET valor = EXCLUDED.valor, conector_id = EXCLUDED.conector_id, atualizado_em = now()
        """,
        (metrica_id, armazem_id, competencia, valor, conector_id),
    )


def gravar_agregados(cur, conector_id: int, agregados: list[dict]) -> int:
    gravadas = 0
    for item in agregados:
        armazem_id = resolver_armazem(cur, conector_id, item["armazem_na_fonte"])
        if armazem_id is None:
            registrar_pendencia(cur, conector_id, item["armazem_na_fonte"])
            continue
        metrica_id = get_or_create_metrica(cur, item["metrica"])
        upsert_medida(cur, metrica_id, armazem_id, item["competencia"], item["valor"], conector_id)
        gravadas += 1
    return gravadas


def iniciar_execucao(cur, conector_id: int, modelo_id, origem: str, arquivo_path) -> int:
    cur.execute(
        """
        INSERT INTO execucoes (conector_id, modelo_id, origem, status, arquivo_path)
        VALUES (%s, %s, %s, 'em_andamento', %s)
        RETURNING id
        """,
        (conector_id, modelo_id, origem, arquivo_path),
    )
    return cur.fetchone()[0]


def finalizar_execucao(cur, execucao_id: int, status: str, linhas_lidas=None, linhas_gravadas=None, erro=None) -> None:
    cur.execute(
        """
        UPDATE execucoes
        SET status = %s, linhas_lidas = %s, linhas_gravadas = %s, erro = %s, finalizado_em = now()
        WHERE id = %s
        """,
        (status, linhas_lidas, linhas_gravadas, erro, execucao_id),
    )
