"""Consultas de linhagem do cockpit (Bloco F / V1.7, tela `/linhagem`).

Grao minimo que o sistema realmente persiste: celula (`medidas`) -> a
recebida que a originou (`medidas_recebidas`, uma por cliente x metrica x
arquivo processado) -> a execucao que processou o arquivo (`execucoes`) -> o
arquivo de origem no SharePoint (cruzando o caminho da execucao com
`processamentos_datahub`, que guarda o `item_id`, e com o inventario em
cache, que guarda o `web_url`).

NAO desce a linha crua da planilha: o processamento (V1.3,
processamento_datahub.py) agrega por cliente e descarta as linhas
individuais depois de agregar -- elas nunca sao persistidas. O grao minimo
real e arquivo x cliente x competencia, nao NF/item de linha.
"""

from . import filiais_datahub, inventario_datahub, serie_datahub

_SEM_CLIENTE = "Sem cliente identificado"


class LinhagemError(Exception):
    """Erro de parametro/estado -- o endpoint traduz pra HTTP 400/404."""


def celulas(cur, metrica: str, competencia: str, filial=None, cliente=None) -> dict:
    """Celulas de `medidas` casadas com o filtro (metrica + competencia,
    filial/cliente opcionais), cada uma com o indicador de se tem origem
    rastreavel -- o detalhe da cadeia sai em `origem_da_celula`."""
    info = serie_datahub.metrica_info(cur, metrica)
    competencia_data = serie_datahub.parse_competencia(competencia, "competencia")

    armazem_id = filial_sigla = None
    if filial:
        armazem_id, filial_sigla = serie_datahub.resolver_filial(cur, filial)
    cliente_id = cliente_nome = None
    if cliente:
        cliente_id, cliente_nome = serie_datahub.resolver_cliente(cur, cliente)

    condicoes = ["m.metrica_id = %s", "m.competencia = %s"]
    params = [info["id"], competencia_data]
    if armazem_id is not None:
        condicoes.append("m.armazem_id = %s")
        params.append(armazem_id)
    if cliente_id is not None:
        condicoes.append("m.cliente_id = %s")
        params.append(cliente_id)
    where = " AND ".join(condicoes)

    cur.execute(
        f"""
        SELECT m.id, a.sigla, c.nome, m.valor, m.origem_tipo, m.medida_recebida_id
        FROM medidas m
        JOIN armazens a ON a.id = m.armazem_id
        LEFT JOIN clientes c ON c.id = m.cliente_id
        WHERE {where}
        ORDER BY a.sigla, c.nome NULLS LAST
        """,
        params,
    )
    linhas = [
        {
            "medida_id": medida_id,
            "filial": sigla,
            "cliente": nome_cliente or _SEM_CLIENTE,
            "valor": float(valor),
            "origem_tipo": origem_tipo,
            "tem_origem_rastreavel": recebida_id is not None,
        }
        for medida_id, sigla, nome_cliente, valor, origem_tipo, recebida_id in cur.fetchall()
    ]

    return {
        "metrica": {
            "nome": info["nome"], "nome_executivo": info["nome_executivo"], "unidade": info["unidade"],
        },
        "filtros": {"competencia": competencia, "filial": filial_sigla, "cliente": cliente_nome},
        "celulas": linhas,
    }


def origem_da_celula(cur, medida_id: int) -> dict:
    """Cadeia de origem de UMA celula: recebida -> execucao -> arquivo.

    Celula sem `medida_recebida_id` (dado legado, anterior a migration 0003,
    ou ajuste manual) declara a limitacao em vez de devolver origem
    inventada."""
    cur.execute("SELECT origem_tipo, medida_recebida_id FROM medidas WHERE id = %s", (medida_id,))
    row = cur.fetchone()
    if row is None:
        raise LinhagemError(f"celula nao encontrada: {medida_id}")
    origem_tipo, recebida_id = row
    if recebida_id is None:
        return {
            "origem_tipo": origem_tipo,
            "rastreavel": False,
            "limitacao": (
                "Celula sem recebida vinculada (dado legado, anterior a linhagem, "
                "ou ajuste manual) -- origem nao reconstruivel."
            ),
        }

    cur.execute(
        """
        SELECT r.arquivo_origem, r.unidade, r.valor, r.criado_em,
               e.id, e.status, e.iniciado_em, e.finalizado_em, e.arquivo_path
        FROM medidas_recebidas r
        JOIN execucoes e ON e.id = r.execucao_id
        WHERE r.id = %s
        """,
        (recebida_id,),
    )
    (arquivo_origem, unidade, valor_recebido, criado_em,
     execucao_id, status_execucao, iniciado_em, finalizado_em, arquivo_path) = cur.fetchone()

    return {
        "origem_tipo": origem_tipo,
        "rastreavel": True,
        "recebida": {
            "arquivo": arquivo_origem,
            "unidade": unidade,
            "valor": float(valor_recebido),
            "criado_em": criado_em.isoformat() if criado_em else None,
        },
        "execucao": {
            "id": execucao_id,
            "status": status_execucao,
            "iniciado_em": iniciado_em.isoformat() if iniciado_em else None,
            "finalizado_em": finalizado_em.isoformat() if finalizado_em else None,
            "caminho": arquivo_path,
        },
        "arquivo": _arquivo_da_execucao(cur, arquivo_path),
    }


def _arquivo_da_execucao(cur, caminho: str | None) -> dict | None:
    """item_id/sigla/web_url do arquivo, cruzando o caminho da execucao com o
    registro de processamento (guarda o item_id) e o inventario em cache
    (guarda o web_url). None quando nao ha match -- nunca inventa."""
    if not caminho:
        return None
    cur.execute(
        "SELECT item_id, unidade, filial FROM processamentos_datahub WHERE caminho = %s",
        (caminho,),
    )
    row = cur.fetchone()
    if row is None:
        return {"caminho": caminho, "item_id": None, "filial_sigla": None, "web_url": None}
    item_id, unidade, filial = row
    arquivo_inventario = inventario_datahub.arquivo_por_item_id(item_id)
    return {
        "caminho": caminho,
        "item_id": item_id,
        "filial_sigla": filiais_datahub.sigla(unidade, filial),
        "web_url": arquivo_inventario.get("web_url") if arquivo_inventario else None,
    }
