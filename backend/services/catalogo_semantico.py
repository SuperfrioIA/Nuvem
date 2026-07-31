"""Consultas do catálogo semântico (Bloco B / V1.1) — leitura das tabelas
`unidades`, `conceitos_canonicos` e `catalogo_campos` pro painel do admin e
pra quem precisar resolver campo -> conceito -> unidade canônica.

Só SELECT: quem escreve é o seed (backend/seed_semantico.py) — mesma regra do
catálogo de métricas (R3). A unidade canônica de um campo é derivada do
conceito, nunca duplicada no campo (uma fonte de verdade só).
"""


def listar_unidades(cur) -> list[dict]:
    cur.execute(
        """
        SELECT chave, nome, categoria, fator_para_base, base_da_categoria, ativo
        FROM unidades
        ORDER BY categoria, base_da_categoria DESC, chave
        """
    )
    return [
        {
            "chave": chave,
            "nome": nome,
            "categoria": categoria,
            "fator_para_base": float(fator) if fator is not None else None,
            "base_da_categoria": base,
            "ativo": ativo,
        }
        for chave, nome, categoria, fator, base, ativo in cur.fetchall()
    ]


def listar_conceitos(cur) -> list[dict]:
    cur.execute(
        """
        SELECT chave, nome, descricao, unidade_canonica, categoria_unidade,
               agregacao_padrao, comparabilidade, versao, vigencia_inicio,
               vigencia_fim, status, observacoes
        FROM conceitos_canonicos
        ORDER BY chave
        """
    )
    return [
        {
            "chave": linha[0],
            "nome": linha[1],
            "descricao": linha[2],
            "unidade_canonica": linha[3],
            "categoria_unidade": linha[4],
            "agregacao_padrao": linha[5],
            "comparabilidade": linha[6],
            "versao": linha[7],
            "vigencia_inicio": linha[8].isoformat() if linha[8] else None,
            "vigencia_fim": linha[9].isoformat() if linha[9] else None,
            "status": linha[10],
            "observacoes": linha[11],
        }
        for linha in cur.fetchall()
    ]


def listar_fontes_com_campos(cur) -> list[dict]:
    """Fontes lógicas que têm mapeamento semântico de campos — alimenta o
    seletor do painel (hoje só a família integrada do DataHub)."""
    cur.execute(
        """
        SELECT f.id, f.chave, f.nome, COUNT(c.id)
        FROM catalogo_fontes f
        JOIN catalogo_campos c ON c.fonte_id = f.id
        GROUP BY f.id, f.chave, f.nome
        ORDER BY f.nome
        """
    )
    return [
        {"id": id_, "chave": chave, "nome": nome, "total_campos": total}
        for id_, chave, nome, total in cur.fetchall()
    ]


def listar_campos(cur, fonte_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT c.posicao, c.nome_original, c.descricao,
               cc.chave, cc.nome, cc.unidade_canonica,
               c.tipo_dado, c.unidade_original, c.unidade_por_coluna,
               c.categoria_unidade, c.transformacao, c.agregacao,
               c.granularidade, c.dim_temporal, c.dim_filial, c.dim_cliente,
               c.obrigatorio, c.status, c.versao, c.observacoes, c.responsavel
        FROM catalogo_campos c
        LEFT JOIN conceitos_canonicos cc ON cc.id = c.conceito_id
        WHERE c.fonte_id = %s
        ORDER BY c.posicao, c.versao
        """,
        (fonte_id,),
    )
    return [
        {
            "posicao": linha[0],
            "nome_original": linha[1],
            "descricao": linha[2],
            "conceito_chave": linha[3],
            "conceito_nome": linha[4],
            # derivada do conceito — o campo não guarda unidade canônica própria
            "unidade_canonica": linha[5],
            "tipo_dado": linha[6],
            "unidade_original": linha[7],
            "unidade_por_coluna": linha[8],
            "categoria_unidade": linha[9],
            "transformacao": linha[10],
            "agregacao": linha[11],
            "granularidade": linha[12],
            "dim_temporal": linha[13],
            "dim_filial": linha[14],
            "dim_cliente": linha[15],
            "obrigatorio": linha[16],
            "status": linha[17],
            "versao": linha[18],
            "observacoes": linha[19],
            "responsavel": linha[20],
        }
        for linha in cur.fetchall()
    ]
