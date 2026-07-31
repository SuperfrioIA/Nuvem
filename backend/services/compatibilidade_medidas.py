"""Compatibilidade de medidas (Bloco B / V1.2) — conversões seguras, bloqueio
de soma incompatível, separação por unidade e auditoria.

Regras (direcionamento V1, seções 5.2/5.3):

- Converter só DENTRO da mesma categoria e só quando as duas unidades têm
  fator conhecido pra base (ex.: t/g/lb -> kg). Nunca inventar conversão.
- Percentual NUNCA soma, nem consigo mesmo.
- Unidade fora do catálogo = categoria "desconhecida": consolida apenas com a
  MESMA unidade literal (ex.: as embalagens do EMB — CXS soma com CXS, nunca
  com PCT nem com kg).
- O que não consolida não é descartado nem escondido: sai separado por
  unidade, com a limitação declarada em texto.

Funções puras: a tabela de unidades entra como dicionário (carregada do banco
por `carregar_tabela`, ou montada na mão nos testes). Nenhum estado global.
"""

from decimal import Decimal


class ConversaoInvalidaError(Exception):
    """Conversão sem regra segura — mensagem sempre explica o porquê."""


def carregar_tabela(cur) -> dict:
    """Tabela de unidades ativa do banco: chave -> {categoria, fator, base}.
    fator é Decimal (coluna NUMERIC) ou None (sem conversão conhecida)."""
    cur.execute(
        """
        SELECT chave, categoria, fator_para_base, base_da_categoria
        FROM unidades WHERE ativo
        """
    )
    return {
        chave: {"categoria": categoria, "fator": fator, "base": base}
        for chave, categoria, fator, base in cur.fetchall()
    }


def _info(unidade, tabela: dict) -> dict:
    return tabela.get(str(unidade)) or {"categoria": "desconhecida", "fator": None, "base": False}


def _base_da_categoria(categoria: str, tabela: dict):
    for chave, info in tabela.items():
        if info["categoria"] == categoria and info["base"]:
            return chave
    return None


def _normalizar_unidade(unidade) -> str:
    """Unidade sempre como texto sem espaços nas pontas; vazia/None vira rótulo
    explícito — nunca o literal 'None' nem grupos duplicados por espaço."""
    texto = str(unidade).strip() if unidade is not None else ""
    return texto or "(sem unidade)"


def converter(valor, de_unidade: str, para_unidade: str, tabela: dict) -> float:
    """Converte valor entre unidades da MESMA categoria com fatores conhecidos.
    Qualquer outro caso levanta ConversaoInvalidaError com o motivo."""
    de_unidade = _normalizar_unidade(de_unidade)
    para_unidade = _normalizar_unidade(para_unidade)
    try:
        valor_num = Decimal(str(valor))
    except Exception as exc:
        raise ConversaoInvalidaError(f"valor não numérico: {valor!r}") from exc
    if de_unidade == para_unidade:
        return float(valor_num)

    de_info, para_info = _info(de_unidade, tabela), _info(para_unidade, tabela)
    if de_info["categoria"] == "desconhecida" or para_info["categoria"] == "desconhecida":
        raise ConversaoInvalidaError(
            f"sem conversão conhecida entre '{de_unidade}' e '{para_unidade}' "
            "(unidade fora do catálogo — não inventar conversão)"
        )
    if de_info["categoria"] != para_info["categoria"]:
        raise ConversaoInvalidaError(
            f"'{de_unidade}' ({de_info['categoria']}) e '{para_unidade}' "
            f"({para_info['categoria']}) são de categorias diferentes — soma/conversão proibida"
        )
    if de_info["categoria"] == "percentual":
        raise ConversaoInvalidaError("percentuais nunca são somados ou convertidos diretamente")
    if de_info["fator"] is None or para_info["fator"] is None:
        raise ConversaoInvalidaError(
            f"sem fator de conversão registrado entre '{de_unidade}' e '{para_unidade}' "
            f"(categoria {de_info['categoria']}) — não inventar conversão"
        )
    fator = Decimal(str(de_info["fator"])) / Decimal(str(para_info["fator"]))
    return float(valor_num * fator)


def podem_consolidar(unidade_a: str, unidade_b: str, tabela: dict) -> tuple[bool, str]:
    """(True, motivo) se A e B podem entrar na mesma soma; (False, motivo) se não."""
    unidade_a, unidade_b = _normalizar_unidade(unidade_a), _normalizar_unidade(unidade_b)
    a, b = _info(unidade_a, tabela), _info(unidade_b, tabela)
    if a["categoria"] == "percentual" or b["categoria"] == "percentual":
        return False, "percentuais nunca são somados diretamente"
    if unidade_a == unidade_b:
        return True, "mesma unidade"
    if a["categoria"] == "desconhecida" or b["categoria"] == "desconhecida":
        return False, (
            f"'{unidade_a}' e '{unidade_b}' não têm compatibilidade conhecida "
            "(unidade fora do catálogo)"
        )
    if a["categoria"] != b["categoria"]:
        return False, (
            f"'{unidade_a}' ({a['categoria']}) + '{unidade_b}' ({b['categoria']}): "
            "categorias diferentes"
        )
    if a["fator"] is None or b["fator"] is None:
        return False, (
            f"'{unidade_a}' e '{unidade_b}' são da categoria {a['categoria']}, "
            "mas não há fator de conversão registrado entre elas"
        )
    return True, f"mesma categoria ({a['categoria']}), conversão pela unidade-base"


def somar_medidas(itens: list[tuple], tabela: dict) -> dict:
    """Soma segura de [(valor, unidade), ...]: consolida só o compatível,
    separa o resto por unidade e devolve auditoria do que aconteceu.

    Retorno:
    - grupos: [{unidade, categoria, total, itens, convertidos}] — um grupo por
      unidade de consolidação (a unidade-base da categoria quando houve
      conversão; a unidade literal quando não há conversão);
    - limitacoes: mensagens das combinações que NÃO consolidaram entre si;
    - auditoria: um registro por item (unidade original -> grupo, fator usado).
    """
    grupos: dict[str, dict] = {}
    auditoria: list[dict] = []
    categorias_nao_consolidaveis: dict[str, set] = {}

    for valor, unidade in itens:
        unidade = _normalizar_unidade(unidade)
        info = _info(unidade, tabela)
        categoria = info["categoria"]

        # percentual NUNCA entra em soma nenhuma -- nem no proprio grupo
        # (somar 50% + 30% e sempre errado). So registra na auditoria.
        if categoria == "percentual":
            auditoria.append(
                {"unidade_original": unidade, "grupo": None,
                 "convertido": False, "categoria": categoria}
            )
            continue

        consolidavel = categoria != "desconhecida" and info["fator"] is not None
        base = _base_da_categoria(categoria, tabela) if consolidavel else None
        if consolidavel and base:
            destino = base
            valor_final = converter(valor, unidade, base, tabela)
            convertido = unidade != base
        else:
            # sem consolidação possível: o grupo é a própria unidade literal
            destino = unidade
            valor_final = float(valor)
            convertido = False
            categorias_nao_consolidaveis.setdefault(categoria, set()).add(unidade)

        grupo = grupos.setdefault(
            destino,
            {"unidade": destino, "categoria": categoria, "total": 0.0,
             "itens": 0, "convertidos": 0},
        )
        grupo["total"] += valor_final
        grupo["itens"] += 1
        if convertido:
            grupo["convertidos"] += 1
        auditoria.append(
            {"unidade_original": unidade, "grupo": destino,
             "convertido": convertido, "categoria": categoria}
        )

    limitacoes = []
    if any(_info(u, tabela)["categoria"] == "percentual" for _, u in itens):
        limitacoes.append("percentuais não foram somados (nunca são aditivos diretamente)")
    for categoria, unidades in sorted(categorias_nao_consolidaveis.items()):
        if len(unidades) > 1:
            limitacoes.append(
                f"unidades sem compatibilidade conhecida ficaram separadas "
                f"({categoria}: {', '.join(sorted(unidades))})"
            )
    if len({g["categoria"] for g in grupos.values()}) > 1:
        limitacoes.append(
            "os grupos são de categorias diferentes — não existe um total geral"
        )

    return {
        "grupos": sorted(grupos.values(), key=lambda g: -g["total"]),
        "limitacoes": limitacoes,
        "auditoria": auditoria,
    }
