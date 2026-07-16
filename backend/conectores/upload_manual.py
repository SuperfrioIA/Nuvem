"""Conector upload_manual: le um xlsx e aplica um modelo de importacao
(mapeamento de colunas, salvo e reutilizavel por relatorio) para produzir o
formato canonico {armazem_na_fonte, competencia, metrica, valor}.

Relatorios reais nao sao tabela limpa armazem x mes -- vem em grao mais fino
(posicao x dia, SKU x lote), com varias colunas candidatas pra mesma dimensao
e cliente misturado nas linhas. O mapeamento por isso:

- armazem / competencia: vem de uma coluna do arquivo OU e um valor fixo
  digitado no upload (relatorio ja recortado pra 1 filial/1 mes).
- metrica: soma direta de uma coluna, ou razao entre duas colunas
  (numerador/denominador) -- necessario pra metricas de nivel/capacidade
  como ocupacao. A razao das somas do periodo ja da o resultado certo mesmo
  com varias linhas por dia dentro do mes.
- coluna de cliente (se houver) e apenas documentada no modelo -- nao vira
  dimensao nem metrica; qualquer coluna nao mapeada some no agrupamento.

Formato "largo" (mes nas colunas) e reconhecido tentando parsear cada
cabecalho como competencia; o que parsear vira coluna de mes, o resto e
ignorado.
"""

import io
import re
from datetime import date, datetime

import openpyxl

from .base import Conector

_MESES_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


class UploadManualConector(Conector):
    def testar(self) -> dict:
        return {"ok": True, "mensagem": "upload manual não depende de conexão externa"}


def ler_colunas(conteudo: bytes) -> list[str]:
    wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    try:
        ws = wb.active
        primeira_linha = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        return [str(c) for c in primeira_linha if c is not None]
    finally:
        wb.close()


def preview(conteudo: bytes, linhas: int = 5) -> dict:
    wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    try:
        ws = wb.active
        todas = ws.iter_rows(values_only=True)
        colunas = [str(c) if c is not None else "" for c in next(todas)]
        amostra = []
        for i, row in enumerate(todas):
            if i >= linhas:
                break
            amostra.append(list(row))
        return {"colunas": colunas, "amostra": amostra}
    finally:
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


def aplicar_modelo(conteudo: bytes, mapeamento: dict) -> tuple[list[dict], int]:
    """Le o arquivo, aplica o mapeamento e devolve os valores ja agregados por
    (armazem_na_fonte, competencia, metrica), junto com a contagem de linhas lidas.
    """
    wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    try:
        ws = wb.active
        linhas_iter = ws.iter_rows(values_only=True)
        cabecalho = [str(c) if c is not None else "" for c in next(linhas_iter)]

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
                    if valor is None or valor == "" or valor in ignorar_valores:
                        continue
                    chave = (armazem_na_fonte, competencia, metrica_fixa)
                    acc = acumulador.setdefault(chave, {"tipo": "soma", "soma": 0.0})
                    acc["soma"] += float(valor)
        else:
            armazem_cfg = mapeamento["armazem"]
            competencia_cfg = mapeamento["competencia"]
            metricas_cfg = mapeamento["metricas"]

            for valores in linhas_iter:
                linhas_lidas += 1
                row = dict(zip(cabecalho, valores))

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
                    ignorar_valores = m.get("ignorar_valores", [])
                    if m["tipo"] == "soma":
                        valor = row.get(m["coluna"])
                        if valor is None or valor == "" or valor in ignorar_valores:
                            continue
                        chave = (armazem_na_fonte, competencia, m["metrica"])
                        acc = acumulador.setdefault(chave, {"tipo": "soma", "soma": 0.0})
                        acc["soma"] += float(valor)
                    elif m["tipo"] == "razao":
                        num = row.get(m["numerador"])
                        den = row.get(m["denominador"])
                        if num is None or den is None or num == "" or den == "":
                            continue
                        if num in ignorar_valores or den in ignorar_valores:
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
        wb.close()
