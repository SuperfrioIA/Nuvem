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


def upsert_medida(
    cur,
    metrica_id: int,
    armazem_id: int,
    competencia,
    valor: float,
    conector_id: int,
    medida_recebida_id: int,
) -> None:
    cur.execute(
        """
        INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, conector_id, medida_recebida_id, origem_tipo)
        VALUES (%s, %s, %s, %s, %s, %s, 'recebida')
        ON CONFLICT (metrica_id, armazem_id, competencia)
        DO UPDATE SET valor = EXCLUDED.valor, conector_id = EXCLUDED.conector_id,
                      medida_recebida_id = EXCLUDED.medida_recebida_id, origem_tipo = 'recebida',
                      atualizado_em = now()
        """,
        (metrica_id, armazem_id, competencia, valor, conector_id, medida_recebida_id),
    )


def registrar_medida_recebida(
    cur, execucao_id: int, armazem_id: int, metrica_id: int, competencia, valor: float
) -> int:
    """Grava o dado agregado que a execucao entregou, antes da publicacao
    canonica -- append-only (reprocessar cria execucao nova, nunca sobrescreve
    uma recebida existente). modelo_versao_id/fonte_id vem denormalizados da
    execucao/modelo pra nao exigir join em toda consulta de auditoria."""
    cur.execute(
        """
        INSERT INTO medidas_recebidas
            (execucao_id, modelo_versao_id, fonte_id, armazem_id, metrica_id, competencia, valor)
        SELECT %s, e.modelo_versao_id, mi.fonte_id, %s, %s, %s, %s
        FROM execucoes e
        LEFT JOIN modelos_importacao mi ON mi.id = e.modelo_id
        WHERE e.id = %s
        RETURNING id
        """,
        (execucao_id, armazem_id, metrica_id, competencia, valor, execucao_id),
    )
    return cur.fetchone()[0]


def gravar_agregados(cur, conector_id: int, execucao_id: int, agregados: list[dict]) -> int:
    gravadas = 0
    for item in agregados:
        armazem_id = resolver_armazem(cur, conector_id, item["armazem_na_fonte"])
        if armazem_id is None:
            registrar_pendencia(cur, conector_id, item["armazem_na_fonte"])
            continue
        metrica_id = get_or_create_metrica(cur, item["metrica"])
        medida_recebida_id = registrar_medida_recebida(
            cur, execucao_id, armazem_id, metrica_id, item["competencia"], item["valor"]
        )
        upsert_medida(cur, metrica_id, armazem_id, item["competencia"], item["valor"], conector_id, medida_recebida_id)
        gravadas += 1
    return gravadas


def registrar_medida_derivada(
    cur,
    metrica_id: int,
    armazem_id: int,
    competencia,
    valor: float,
    regra_codigo: str,
    regra_versao: str,
    origens: list[tuple[str, int, str | None]] = (),
) -> int:
    """Grava uma medida canonica derivada (origem_tipo='derivada') e sua
    linhagem (delete+insert, mesmo padrao de reprocesso do projeto). `origens`
    e uma lista de (medida_origem_tipo, medida_origem_id, papel_origem).

    Nao chamada por nenhuma regra de negocio ainda -- so prova a estrutura pro
    Lote 9 (ocupacao real = varias parcelas), que vai usa-la de verdade.
    """
    cur.execute(
        """
        INSERT INTO medidas (metrica_id, armazem_id, competencia, valor, origem_tipo, regra_codigo, regra_versao, calculado_em)
        VALUES (%s, %s, %s, %s, 'derivada', %s, %s, now())
        ON CONFLICT (metrica_id, armazem_id, competencia)
        DO UPDATE SET valor = EXCLUDED.valor, origem_tipo = 'derivada',
                      regra_codigo = EXCLUDED.regra_codigo, regra_versao = EXCLUDED.regra_versao,
                      calculado_em = now(), medida_recebida_id = NULL, atualizado_em = now()
        RETURNING id
        """,
        (metrica_id, armazem_id, competencia, valor, regra_codigo, regra_versao),
    )
    medida_id = cur.fetchone()[0]

    cur.execute("DELETE FROM medida_linhagem WHERE medida_id = %s", (medida_id,))
    for origem_tipo, origem_id, papel_origem in origens:
        cur.execute(
            """
            INSERT INTO medida_linhagem (medida_id, medida_origem_tipo, medida_origem_id, papel_origem)
            VALUES (%s, %s, %s, %s)
            """,
            (medida_id, origem_tipo, origem_id, papel_origem),
        )
    return medida_id


def iniciar_execucao(cur, conector_id: int, modelo_id, modelo_versao_id, origem: str, arquivo_path) -> int:
    cur.execute(
        """
        INSERT INTO execucoes (conector_id, modelo_id, modelo_versao_id, origem, status, arquivo_path)
        VALUES (%s, %s, %s, %s, 'em_andamento', %s)
        RETURNING id
        """,
        (conector_id, modelo_id, modelo_versao_id, origem, arquivo_path),
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
