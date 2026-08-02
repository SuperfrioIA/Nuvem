"""Leitura controlada da familia ENTRADA_MERCADORIAS do SharePoint DataHub
(Lote P3).

Nao e um leitor generico de planilha -- so entende esta familia especifica
(nome, aba e cabecalho fixos, documentados em docs/FONTES_DATAHUB.md). O
caminho generico de leitura continua sendo o dos modelos de importacao
(backend/conectores/upload_manual.py).

Guarda de seguranca: item_id so e aceito se aparecer na lista de arquivos da
ultima sincronizacao do Lote P2 (backend/services/inventario_datahub.py) --
nunca um id digitado ou uma URL externa. Alem disso, o nome do arquivo tem que
bater no padrao ENTRADA_MERCADORIAS_{filial}_{AAMM}.xlsx, a extensao tem que
ser .xlsx e a aba tem que se chamar SLIN -- qualquer uma falhando, erro claro
(EntradaMercadoriasError).

openpyxl nao e o Excel e nao executa macro -- read_only=True e data_only=True
atendem a exigencia de "sem macro" por construcao, sem checagem extra.

Colunas sao localizadas por nome (dicionario cabecalho->indice montado na
leitura), nunca por posicao chumbada -- se a planilha ganhar uma coluna nova
amanha, a leitura continua funcionando. Posicao so seria necessaria pra
desempatar o rotulo duplicado (EMB aparece duas vezes), mas nenhuma coluna
candidata a KPI usa EMB, entao a primeira ocorrencia basta.
"""

import io
import os
import re

import openpyxl

from . import graph_datahub, inventario_datahub

_ABA_ESPERADA = "SLIN"

_PADRAO_NOME = re.compile(r"^ENTRADA_MERCADORIAS_(\d+)_(\d{2})(\d{2})\.xlsx$", re.IGNORECASE)

# As 20 colunas do export real (docs/FONTES_DATAHUB.md) -- todas obrigatorias
# no cabecalho (decisao de 29/jul/2026: validar todas, nao so as dos KPIs do
# P4). EMB aparece duas vezes de proposito (posicoes 10 e 12 no arquivo real).
_COLUNAS_ESPERADAS = (
    "Cliente", "Cliente CNPJ", "GEM", "Devolução", "Solicitação", "NF Entrada",
    "Código", "Descrição", "Volume", "EMB", "Fração", "EMB", "Peso Líquido",
    "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA", "Código Estoque",
    "Nome Estoque", "Operação",
)

# So estas recebem validacao de valor (parse numerico, linha descartada se
# falhar) -- as outras 14 sao lidas cruas, sem formato esperado definido
# (decisao de 29/jul/2026).
_COLUNAS_NUMERICAS = (
    "Volume", "Peso Líquido", "Peso Bruto", "Vlr. Unitário", "Vlr. Total", "Qtde UA",
)


class EntradaMercadoriasError(Exception):
    """Erro de validacao do item/arquivo/aba/coluna -- mensagem sempre clara
    pro chamador (endpoint traduz pra HTTP 400)."""


def _limite_bytes() -> int:
    """Mesmo limite do upload manual (UPLOAD_MAX_MB, default 50 MB) -- os
    arquivos desta familia tem ~400 KB, folga enorme; sem variavel nova."""
    limite_mb = int(os.environ.get("UPLOAD_MAX_MB", "50"))
    return limite_mb * 1024 * 1024


def _arquivo_do_inventario(item_id: str) -> dict:
    """So aceita item_id que apareceu na ultima sincronizacao do P2 -- o cache
    vira lista de permissao (fonte unica: inventario_datahub.arquivo_por_item_id).
    Sem sincronizacao ainda, ou id desconhecido, falha com mensagem clara em vez
    de tentar baixar de qualquer forma."""
    if not inventario_datahub.status().get("resumo"):
        raise EntradaMercadoriasError(
            "nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro"
        )
    arquivo = inventario_datahub.arquivo_por_item_id(item_id)
    if arquivo is None:
        raise EntradaMercadoriasError(
            "item_id nao encontrado na ultima sincronizacao do DataHub"
        )
    return arquivo


def dados_da_familia(nome) -> tuple[str, str] | None:
    """(filial, competencia) quando o nome pertence a familia
    ENTRADA_MERCADORIAS; None caso contrario (V1.3 usa pra listar e rotular o
    que processar)."""
    m = _PADRAO_NOME.match(nome or "")
    if not m:
        return None
    filial, aa, mm = m.group(1), m.group(2), m.group(3)
    return filial, f"20{aa}-{mm}"


def _validar_nome(nome: str) -> tuple[str, str]:
    if not nome.lower().endswith(".xlsx"):
        raise EntradaMercadoriasError(f"extensao invalida (esperado .xlsx): {nome}")

    dados = dados_da_familia(nome)
    if dados is None:
        raise EntradaMercadoriasError(
            "nome de arquivo fora do padrao "
            f"ENTRADA_MERCADORIAS_{{filial}}_{{AAMM}}.xlsx: {nome}"
        )
    return dados


def _abrir_aba(conteudo: bytes):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as exc:
        raise EntradaMercadoriasError("arquivo nao e um .xlsx valido ou esta corrompido") from exc

    if _ABA_ESPERADA not in wb.sheetnames:
        wb.close()
        raise EntradaMercadoriasError(f"aba '{_ABA_ESPERADA}' nao encontrada no arquivo")
    return wb


def _indice_cabecalho(linha_cabecalho) -> dict[str, int]:
    indice: dict[str, int] = {}
    for i, valor in enumerate(linha_cabecalho):
        nome = str(valor).strip() if valor is not None else ""
        if nome and nome not in indice:
            indice[nome] = i

    faltando = sorted({c for c in _COLUNAS_ESPERADAS if c not in indice})
    if faltando:
        raise EntradaMercadoriasError("coluna(s) nao encontrada(s): " + ", ".join(faltando))
    return indice


def _paranum_br(valor):
    """Aceita numero ja nativo (openpyxl le celula numerica como int/float) ou
    texto no formato BR (ponto de milhar, virgula decimal: '1.234,56').
    Devolve None se nao for nenhum dos dois -- linha e descartada."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def item_mais_recente() -> str:
    """item_id do arquivo ENTRADA_MERCADORIAS mais recente no inventario.

    Decisao de 29/jul/2026: a tela de KPIs (Lote P4) nao deixa escolher entre
    os arquivos da familia (tem ate 20, filial x competencia) -- sempre mostra
    o mais recente sincronizado, mais simples pro POC.
    """
    resumo = inventario_datahub.status().get("resumo")
    if not resumo:
        raise EntradaMercadoriasError(
            "nenhuma sincronizacao do DataHub ainda -- clique em 'Sincronizar agora' primeiro"
        )
    candidatos = [a for a in resumo.get("arquivos", []) if _PADRAO_NOME.match(a.get("nome", ""))]
    if not candidatos:
        raise EntradaMercadoriasError(
            "nenhum arquivo ENTRADA_MERCADORIAS encontrado na ultima sincronizacao"
        )
    mais_recente = max(candidatos, key=lambda a: a.get("modificado_em") or "")
    return mais_recente["id"]


def ler(item_id: str) -> dict:
    """Baixa, valida e le a planilha; devolve metadados + linhas validadas.

    Todas as linhas validas ficam em memoria (o Lote P4 vai precisar delas
    pra somar os KPIs) -- quem expoe isso via HTTP decide quanto devolver.
    """
    arquivo = _arquivo_do_inventario(item_id)
    nome = arquivo["nome"]
    filial, competencia = _validar_nome(nome)

    conteudo = graph_datahub.baixar_item(item_id, limite_bytes=_limite_bytes())

    wb = _abrir_aba(conteudo)
    try:
        ws = wb[_ABA_ESPERADA]
        linhas = ws.iter_rows(values_only=True)
        try:
            cabecalho = next(linhas)
        except StopIteration as exc:
            raise EntradaMercadoriasError("arquivo vazio -- sem linha de cabecalho") from exc

        indice = _indice_cabecalho(cabecalho)
        colunas_unicas = list(dict.fromkeys(_COLUNAS_ESPERADAS))

        linhas_validas: list[dict] = []
        lidas = 0
        descartadas = 0
        for linha in linhas:
            if linha is None or all(v is None for v in linha):
                continue
            lidas += 1

            registro = {}
            valida = True
            for coluna in colunas_unicas:
                pos = indice[coluna]
                valor_bruto = linha[pos] if pos < len(linha) else None
                if coluna in _COLUNAS_NUMERICAS:
                    numero = _paranum_br(valor_bruto)
                    if numero is None:
                        valida = False
                        break
                    registro[coluna] = numero
                else:
                    registro[coluna] = valor_bruto

            if valida:
                linhas_validas.append(registro)
            else:
                descartadas += 1

        if lidas == 0:
            raise EntradaMercadoriasError("arquivo sem linhas de dado (so cabecalho)")
    finally:
        wb.close()

    total_validas = len(linhas_validas)
    qualidade_pct = round(100 * total_validas / lidas, 1) if lidas else 0.0

    return {
        "arquivo": nome,
        "caminho": arquivo.get("caminho"),
        "modificado_em": arquivo.get("modificado_em"),
        "tamanho": arquivo.get("tamanho"),
        "filial": filial,
        "competencia": competencia,
        "linhas_lidas": lidas,
        "linhas_validas": total_validas,
        "linhas_descartadas": descartadas,
        "qualidade_pct": qualidade_pct,
        "linhas": linhas_validas,
    }
