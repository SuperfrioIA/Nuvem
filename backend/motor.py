"""Motor de scores: desvio de cada medida vs o proprio historico.

Por metrica x armazem, media e desvio-padrao (amostral) da janela de ate 24
competencias anteriores (exclui o mes em analise); z-score vira estado. Python
puro (stdlib `statistics`), sem libs de ML -- decisao de arquitetura.

Sempre recalcula tudo (delete+insert): scores sao cache derivado/recalculavel,
nao fonte de verdade (ver docs/ARQUITETURA.md), e o volume do piloto e pequeno
o bastante pra recalculo seletivo nao compensar a complexidade.
"""

import statistics

JANELA_MAXIMA = 24
HISTORICO_MINIMO = 6
LIMIAR_Z = 2


def calcular_scores(cur) -> int:
    cur.execute("SELECT DISTINCT metrica_id, armazem_id FROM medidas")
    pares = cur.fetchall()

    cur.execute("DELETE FROM scores")

    gravados = 0
    for metrica_id, armazem_id in pares:
        # soma por competencia: desde o V1.3 a mesma celula (metrica x armazem
        # x competencia) pode ter varias linhas (grao cliente, DataHub) -- a
        # serie do score e sempre a da FILIAL (total = soma; so metricas
        # aditivas sao persistidas no grao cliente). Pra metrica com uma linha
        # por celula (todas as anteriores), a soma devolve o proprio valor.
        cur.execute(
            """
            SELECT competencia, SUM(valor)
            FROM medidas
            WHERE metrica_id = %s AND armazem_id = %s
            GROUP BY competencia
            ORDER BY competencia
            """,
            (metrica_id, armazem_id),
        )
        pontos = cur.fetchall()

        for i, (competencia, valor) in enumerate(pontos):
            historico = [float(v) for _, v in pontos[max(0, i - JANELA_MAXIMA):i]]

            if len(historico) < HISTORICO_MINIMO:
                _inserir_score(cur, metrica_id, armazem_id, competencia, None, None, None, "historico_curto")
                gravados += 1
                continue

            media = statistics.mean(historico)
            desvio = statistics.stdev(historico)
            valor_f = float(valor)

            if desvio == 0:
                z = 0.0 if valor_f == media else None
                estado = "normal" if valor_f == media else "fora_padrao"
            else:
                z = (valor_f - media) / desvio
                estado = "fora_padrao" if abs(z) >= LIMIAR_Z else "normal"

            _inserir_score(cur, metrica_id, armazem_id, competencia, media, desvio, z, estado)
            gravados += 1

    return gravados


def _inserir_score(cur, metrica_id, armazem_id, competencia, media, desvio, z, estado) -> None:
    cur.execute(
        """
        INSERT INTO scores (metrica_id, armazem_id, competencia, media, desvio_padrao, z_score, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (metrica_id, armazem_id, competencia, media, desvio, z, estado),
    )
