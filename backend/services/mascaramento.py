"""Mascaramento de dado pessoal/de cliente antes de qualquer envio a provedor
de IA (Bloco E / V1.5).

Requisito fixado no fechamento do Bloco D: a sessao do Laboratorio grava a
amostra CRUA (decisao da Maria -- ver `laboratorio.py`); mascarar e obrigacao
de quem MONTA O CONTEXTO pra IA (laboratorio_chat.py), nunca da gravacao da
sessao. `mascarar_perfil_arquivo` nunca muta o perfil recebido -- devolve uma
copia so com os pontos sensiveis trocados; a tela e o historico da sessao
continuam mostrando o perfil original, sem mascara.

Quatro pontos onde o perfil determinístico (perfil_dados.py) guarda nome/CNPJ
de cliente em claro, achados na revisao deste lote (o quarto so na
verificacao independente -- os tres primeiros vazam por serem exibidos, o
quarto porque o proprio USUARIO digita o nome no filtro e o perfil ecoa esse
texto de volta):
- amostra.linhas: a celula crua da coluna de cliente/CNPJ;
- clientes.top: contagem por cliente, com o nome em claro;
- colunas[].exemplos: coluna de texto guarda até 3 valores distintos em
  claro -- a coluna de cliente/CNPJ nunca e numerica, entao os exemplos sao
  nome/CNPJ reais quando essa coluna existe;
- limitacoes: quando a sessao usa filtro de cliente, `perfil_dados._limitacoes`
  grava "Perfil calculado APÓS filtro de cliente (<nome digitado>): ..." --
  o valor vem de `filtro_aplicado.valores`, texto livre do usuario, não da
  planilha, mas igualmente sensível.

Pseudonimo consistente DENTRO do arquivo (mesmo cliente = mesmo pseudonimo
nos quatro pontos, com um mapa so, normalizado por minusculo+strip -- "SAPORE"
na amostra e "sapore" digitado no filtro caem no mesmo pseudonimo) -- a IA
continua podendo raciocinar sobre concentracao/agrupamento sem ver a
identidade real. Sem consistencia ENTRE arquivos: casar os mapas exigiria
expor o de-para em algum lugar, contra o proposito do mascaramento.

Funcao pura: um dict de entrada (o perfil de UM arquivo, no formato que
perfil_dados.perfilar devolve), um dict de saida. Nenhum acesso a banco,
nenhuma chamada de rede.
"""

import re


def _colunas_sensiveis(perfil_arquivo: dict) -> set[int]:
    """Posicoes de coluna que carregam dado pessoal/de cliente: a coluna
    identificada como dimensao cliente pelo perfil (catalogo ou heuristica) e
    qualquer coluna cujo rotulo contenha CNPJ."""
    coluna_cliente = (perfil_arquivo.get("clientes") or {}).get("coluna")
    posicoes = set()
    for coluna in perfil_arquivo["colunas"]:
        nome = coluna["nome"]
        if nome == coluna_cliente or "cnpj" in nome.strip().lower():
            posicoes.add(coluna["posicao"])
    return posicoes


def _valores_do_filtro_de_cliente(perfil_arquivo: dict) -> list:
    filtro = perfil_arquivo.get("filtro_aplicado") or {}
    return filtro["valores"] if filtro.get("tipo") == "cliente" else []


def _pseudonimo(valor, mapa: dict):
    if valor is None or str(valor).strip() == "":
        return valor
    chave = str(valor).strip().lower()
    if chave not in mapa:
        mapa[chave] = f"CLIENTE_{len(mapa) + 1}"
    return mapa[chave]


def _mascarar_texto(texto: str, valores_crus: list, mapa: dict) -> str:
    """Troca cada valor cru (do filtro de cliente) pelo pseudonimo dele, onde
    aparecer dentro de `texto` -- sem diferenciar caixa (o filtro compara
    `.lower()`, então "SAPORE" e "sapore" têm que casar aqui também)."""
    for valor in valores_crus:
        if not valor:
            continue
        pseudonimo = _pseudonimo(valor, mapa)
        texto = re.sub(re.escape(str(valor)), str(pseudonimo), texto, flags=re.IGNORECASE)
    return texto


def mascarar_perfil_arquivo(perfil_arquivo: dict) -> dict:
    """Copia do perfil de um arquivo com cliente/CNPJ trocados por pseudonimo
    em amostra, clientes.top, colunas[].exemplos e limitacoes. Sem coluna
    sensivel identificada nem filtro de cliente aplicado, devolve o mesmo
    dict recebido (nada a mascarar)."""
    posicoes = _colunas_sensiveis(perfil_arquivo)
    valores_filtro = _valores_do_filtro_de_cliente(perfil_arquivo)
    if not posicoes and not valores_filtro:
        return perfil_arquivo

    mapa: dict = {}
    mascarado = dict(perfil_arquivo)

    if posicoes:
        amostra = perfil_arquivo["amostra"]
        linhas_mascaradas = []
        for linha in amostra["linhas"]:
            nova = list(linha)
            for posicao in sorted(posicoes):
                indice = posicao - 1
                if indice < len(nova):
                    nova[indice] = _pseudonimo(nova[indice], mapa)
            linhas_mascaradas.append(nova)
        mascarado["amostra"] = {"colunas": amostra["colunas"], "linhas": linhas_mascaradas}

        colunas_mascaradas = []
        for coluna in perfil_arquivo["colunas"]:
            if coluna["posicao"] in posicoes and coluna.get("exemplos"):
                coluna = {**coluna, "exemplos": [_pseudonimo(v, mapa) for v in coluna["exemplos"]]}
            colunas_mascaradas.append(coluna)
        mascarado["colunas"] = colunas_mascaradas

        clientes = perfil_arquivo.get("clientes")
        if clientes and clientes.get("top"):
            mascarado["clientes"] = {
                **clientes,
                "top": [
                    {**item, "valor": _pseudonimo(item["valor"], mapa)} for item in clientes["top"]
                ],
            }

    limitacoes = perfil_arquivo.get("limitacoes")
    if valores_filtro and limitacoes:
        mascarado["limitacoes"] = [
            _mascarar_texto(texto, valores_filtro, mapa) for texto in limitacoes
        ]

    return mascarado
