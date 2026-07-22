"""Conector upload_manual: le um xlsx ou csv e aplica um modelo de importacao
(mapeamento de colunas, salvo e reutilizavel por relatorio) para produzir o
formato canonico {armazem_na_fonte, competencia, metrica, valor}.

Relatorios reais nao sao tabela limpa armazem x mes -- vem em grao mais fino
(posicao x dia, SKU x lote), com varias colunas candidatas pra mesma dimensao
e cliente misturado nas linhas. O mapeamento por isso:

- armazem / competencia: vem de uma coluna do arquivo OU e um valor fixo
  digitado no upload (relatorio ja recortado pra 1 filial/1 mes).
- metrica: soma direta de uma coluna, soma de varias colunas (mesma linha --
  necessario quando a fonte quebra a mesma metrica por subtipo, ex.: ocupacao
  manual por estrutura PPA/DRV/BLC/PSH/UNI), ou razao entre duas colunas
  (numerador/denominador -- necessario pra metricas de nivel/capacidade como
  ocupacao). A razao das somas do periodo ja da o resultado certo mesmo com
  varias linhas por dia dentro do mes. `divisor` (soma/soma_colunas) converte
  unidade sem chumbar a conta no valor bruto (ex.: peso em kg -> toneladas).
- filtro de linha: `filtros` no nivel do modelo (aplica a toda metrica --
  ex.: excluir instancia de teste do DW) ou no nivel da metrica (ex.: separar
  recebimento de expedicao pela mesma coluna de operacao).
- coluna de cliente (se houver) e apenas documentada no modelo -- nao vira
  dimensao nem metrica; qualquer coluna nao mapeada some no agrupamento.

Formato "largo" (mes nas colunas) e reconhecido tentando parsear cada
cabecalho como competencia; o que parsear vira coluna de mes, o resto e
ignorado. Filtros de linha nao se aplicam a esse formato (nenhuma fonte do
Lote 8 precisa dele).
"""

import csv
import io
import re
from datetime import date, datetime

import openpyxl

from .base import Conector

_MESES_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

_OPERADORES = {
    "igual": lambda v, alvo: str(v).strip() == str(alvo),
    "diferente": lambda v, alvo: str(v).strip() != str(alvo),
    "vazio": lambda v, alvo: v is None or str(v).strip() == "",
    "nao_vazio": lambda v, alvo: v is not None and str(v).strip() != "",
    "maior_igual": lambda v, alvo: _paranum(v) is not None and _paranum(v) >= alvo,
    "menor_igual": lambda v, alvo: _paranum(v) is not None and _paranum(v) <= alvo,
}


class UploadManualConector(Conector):
    def testar(self) -> dict:
        return {"ok": True, "mensagem": "upload manual não depende de conexão externa"}


def _eh_csv(nome_arquivo: str | None) -> bool:
    return bool(nome_arquivo) and nome_arquivo.lower().endswith(".csv")


def _abrir(conteudo: bytes, nome_arquivo: str | None):
    """Devolve (cabecalho, iterador_de_linhas, workbook_ou_None). Quem chama
    fecha o workbook (xlsx) se vier preenchido; csv não tem recurso a fechar."""
    if _eh_csv(nome_arquivo):
        texto = conteudo.decode("utf-8-sig")
        leitor = csv.reader(io.StringIO(texto), delimiter=";", quotechar='"')
        linhas = iter(leitor)
        cabecalho = [c.strip() for c in next(linhas)]
        return cabecalho, linhas, None

    wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    ws = wb.active
    linhas = ws.iter_rows(values_only=True)
    cabecalho = [str(c) if c is not None else "" for c in next(linhas)]
    return cabecalho, linhas, wb


def _paranum(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _passa_filtros(row: dict, filtros: list[dict]) -> bool:
    for f in filtros:
        valor = row.get(f["coluna"])
        operador = _OPERADORES[f["operador"]]
        if not operador(valor, f.get("valor")):
            return False
    return True


def _ignorado(valor, ignorar_valores: list) -> bool:
    if not ignorar_valores:
        return False
    if valor in ignorar_valores:
        return True
    numero = _paranum(valor)
    if numero is None:
        return False
    return any(numero == _paranum(iv) for iv in ignorar_valores)


def ler_colunas(conteudo: bytes, nome_arquivo: str | None = None) -> list[str]:
    cabecalho, _linhas, wb = _abrir(conteudo, nome_arquivo)
    if wb is not None:
        wb.close()
    return cabecalho


def preview(conteudo: bytes, nome_arquivo: str | None = None, linhas: int = 5) -> dict:
    cabecalho, todas, wb = _abrir(conteudo, nome_arquivo)
    try:
        amostra = []
        for i, row in enumerate(todas):
            if i >= linhas:
                break
            amostra.append(list(row))
        return {"colunas": cabecalho, "amostra": amostra}
    finally:
        if wb is not None:
            wb.close()


def _parse_competencia(valor, formato_data: str | None = None) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date().replace(day=1)
    if isinstance(valor, date):
        return valor.replace(day=1)

    texto = str(valor).strip()
    if not texto:
        return None

    if formato_data:
        try:
            return datetime.strptime(texto, formato_data).date().replace(day=1)
        except ValueError:
            pass

    m = re.match(r"^(\d{4})-(\d{2})", texto)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)

    m = re.match(r"^([A-Za-zçÇ]{3})/(\d{2,4})$", texto)
    if m:
        mes = _MESES_PT.get(m.group(1).lower())
        ano = int(m.group(2))
        if ano < 100:
            ano += 2000
        if mes:
            return date(ano, mes, 1)

    raise ValueError(f"competência não reconhecida: {valor!r}")


def _resolver_armazem(row: dict, cfg: dict) -> str | None:
    if cfg["tipo"] == "fixo":
        return str(cfg["valor"]).strip()
    valor = row.get(cfg["coluna"])
    if valor is None or str(valor).strip() == "":
        return None
    return str(valor).strip()


def aplicar_modelo(conteudo: bytes, mapeamento: dict, nome_arquivo: str | None = None) -> tuple[list[dict], int]:
    """Le o arquivo, aplica o mapeamento e devolve os valores ja agregados por
    (armazem_na_fonte, competencia, metrica), junto com a contagem de linhas lidas.
    """
    cabecalho, linhas_iter, wb = _abrir(conteudo, nome_arquivo)
    try:
        formato = mapeamento.get("formato", "longo")
        acumulador: dict[tuple, dict] = {}
        linhas_lidas = 0

        if formato == "largo":
            colunas_competencia = {}
            for nome_col in cabecalho:
                try:
                    competencia = _parse_competencia(nome_col)
                except ValueError:
                    competencia = None
                if competencia:
                    colunas_competencia[nome_col] = competencia

            armazem_cfg = mapeamento["armazem"]
            metrica_fixa = mapeamento["metrica_fixa"]
            ignorar_valores = mapeamento.get("ignorar_valores", [])

            for valores in linhas_iter:
                linhas_lidas += 1
                row = dict(zip(cabecalho, valores))
                armazem_na_fonte = _resolver_armazem(row, armazem_cfg)
                if not armazem_na_fonte:
                    continue
                for nome_col, competencia in colunas_competencia.items():
                    valor = row.get(nome_col)
                    if valor is None or valor == "" or _ignorado(valor, ignorar_valores):
                        continue
                    chave = (armazem_na_fonte, competencia, metrica_fixa)
                    acc = acumulador.setdefault(chave, {"tipo": "soma", "soma": 0.0})
                    acc["soma"] += float(valor)
        else:
            armazem_cfg = mapeamento["armazem"]
            competencia_cfg = mapeamento["competencia"]
            metricas_cfg = mapeamento["metricas"]
            filtros_modelo = mapeamento.get("filtros", [])

            for valores in linhas_iter:
                linhas_lidas += 1
                row = dict(zip(cabecalho, valores))

                if not _passa_filtros(row, filtros_modelo):
                    continue

                armazem_na_fonte = _resolver_armazem(row, armazem_cfg)
                if not armazem_na_fonte:
                    continue

                if competencia_cfg["tipo"] == "fixo":
                    competencia_bruta = competencia_cfg["valor"]
                else:
                    competencia_bruta = row.get(competencia_cfg["coluna"])
                try:
                    competencia = _parse_competencia(competencia_bruta, competencia_cfg.get("formato_data"))
                except ValueError:
                    continue
                if not competencia:
                    continue

                for m in metricas_cfg:
                    if not _passa_filtros(row, m.get("filtros", [])):
                        continue
                    ignorar_valores = m.get("ignorar_valores", [])
                    divisor = m.get("divisor", 1)

                    if m["tipo"] == "soma":
                        valor = row.get(m["coluna"])
                        if valor is None or valor == "" or _ignorado(valor, ignorar_valores):
                            continue
                        chave = (armazem_na_fonte, competencia, m["metrica"])
                        acc = acumulador.setdefault(chave, {"tipo": "soma", "soma": 0.0})
                        acc["soma"] += float(valor) / divisor
                    elif m["tipo"] == "soma_colunas":
                        total = 0.0
                        algum_valor = False
                        for col in m["colunas"]:
                            valor = row.get(col)
                            if valor is None or valor == "" or _ignorado(valor, ignorar_valores):
                                continue
                            total += float(valor)
                            algum_valor = True
                        if not algum_valor:
                            continue
                        chave = (armazem_na_fonte, competencia, m["metrica"])
                        acc = acumulador.setdefault(chave, {"tipo": "soma", "soma": 0.0})
                        acc["soma"] += total / divisor
                    elif m["tipo"] == "razao":
                        num = row.get(m["numerador"])
                        den = row.get(m["denominador"])
                        if num is None or den is None or num == "" or den == "":
                            continue
                        if _ignorado(num, ignorar_valores) or _ignorado(den, ignorar_valores):
                            continue
                        chave = (armazem_na_fonte, competencia, m["metrica"])
                        acc = acumulador.setdefault(chave, {"tipo": "razao", "num": 0.0, "den": 0.0})
                        acc["num"] += float(num)
                        acc["den"] += float(den)

        resultado = []
        for (armazem_na_fonte, competencia, metrica), acc in acumulador.items():
            if acc["tipo"] == "soma":
                valor = acc["soma"]
            else:
                if acc["den"] == 0:
                    continue
                valor = acc["num"] / acc["den"]
            resultado.append(
                {
                    "armazem_na_fonte": armazem_na_fonte,
                    "competencia": competencia,
                    "metrica": metrica,
                    "valor": valor,
                }
            )
        return resultado, linhas_lidas
    finally:
        if wb is not None:
            wb.close()
