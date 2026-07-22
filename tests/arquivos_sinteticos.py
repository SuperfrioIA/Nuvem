"""Arquivos SINTETICOS minimos, um por familia de fonte da POC.

Gerados em memoria com as colunas reais de cada export (conforme o catalogo do
Lote 8.5) e valores inventados, escolhidos pra dar totais conferiveis a mao.
Nao sao amostras dos arquivos reais — provam a mecanica do parser/ingestao com
os mapeamentos reais (tests/modelos_reais.py), nao a qualidade do dado real.
"""

import io

import openpyxl


def _csv(linhas: list[list], sep: str = ";") -> bytes:
    texto = "\n".join(sep.join("" if c is None else str(c) for c in linha) for linha in linhas)
    return texto.encode("utf-8")


def _xlsx(linhas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def pos_sum_xlsx() -> bytes:
    """Foto de 15/07/2026, RMSPIII com 3 camaras (1 virtual: Local vazio) e RPI.

    Esperado (RMSPIII, 2026-07): posicoes_ocupadas=9773, posicoes_virtuais=578,
    capacidade_total=12170, capacidade_bloqueada=840, capacidade_disponivel=11330.
    Esperado (RPI, 2026-07): ocupadas=1000, virtuais nada (sem linha de Local
    vazio -> metrica nem aparece), total=2000, bloqueada=100, disponivel=1900.
    """
    return _xlsx(
        [
            ["Data", "Empresa", "Filial", "Tipo", "Local", "Temp",
             "Cap Tot", "Cap Blq", "Cap Dsp", "Ocup Peso Líquido",
             "Ocup Peso Bruto", "Ocup LPN", "Ocup Pos"],
            ["15/07/2026", "SF", "RMSPIII", "Câmara", "CAM01", "CG",
             6000, 500, 5500, 0, 0, 0, 4000],
            ["15/07/2026", "SF", "RMSPIII", "Câmara", "CAM02", "CG",
             6170, 340, 5830, 0, 0, 0, 5195],
            ["15/07/2026", "SF", "RMSPIII", "Câmara", None, "CG",
             0, 0, 0, 0, 0, 0, 578],
            ["15/07/2026", "SF", "RPI", "Câmara", "CAM01", "CG",
             2000, 100, 1900, 0, 0, 0, 1000],
        ]
    )


def capacidade_hdr_csv() -> bytes:
    """Cadastro de capacidade. Esperado (competencia fixa 2026-07):
    RMSPIII total=12170/blq=840/dsp=11330; RPI total=2000/blq=100/dsp=1900."""
    return _csv(
        [
            ["PK_CAPACIDADE_HDR", "FK_EMPRESA", "FK_FILIAL", "WMS_ENTITY_ID",
             "CAPACIDADE_POS_TOT_QTD", "CAPACIDADE_POS_BLQ_QTD", "CAPACIDADE_POS_DSP_QTD"],
            [1, 1, 46, "RMSPIII", 12170, 840, 11330],
            [2, 1, 3, "RPI", 2000, 100, 1900],
        ]
    )


def ocupacao_comercial_csv() -> bytes:
    """Contratos take-or-pay. FK_FILIAL numerico (46=RMSPIII no de-para).
    Esperado: comercial_vigente RMSPIII 2026-07 = 3697 + 6076 = 9773."""
    return _csv(
        [
            ["PK_OCUPACAO_COM", "FK_EMPRESA", "FK_FILIAL", "FK_CLIENTE",
             "TIPO_ACORDO", "DATA_INICIAL", "DATA_FINAL", "OCUPACAO_POSICAO_QTD"],
            [1, 1, 46, 67945071, "P", "2025-01-01", "2026-12-31", 3697],
            [2, 1, 46, 49930514, "P", "2025-01-01", "2026-12-31", 6076],
        ]
    )


def ocupacao_manual_csv() -> bytes:
    """Digitacao manual. FK_FILIAL 30 = RMSP no de-para; duas linhas do mesmo
    dia (locais diferentes) somam. Esperado: ocupacao_manual RMSP 2026-07 =
    (100+200+300+0+50) + (25+0+0+0+25) = 700."""
    return _csv(
        [
            ["PK_OCUPACAO_MANUAL", "DW_DATA_INCLUSAO", "FK_EMPRESA", "FK_FILIAL",
             "OCUPACAO_POSICAO_QTD_PPA", "OCUPACAO_POSICAO_QTD_DRV",
             "OCUPACAO_POSICAO_QTD_BLC", "OCUPACAO_POSICAO_QTD_PSH",
             "OCUPACAO_POSICAO_QTD_UNI"],
            [1, "2026-07-15 08:00:00", 1, 30, 100, 200, 300, 0, 50],
            [2, "2026-07-15 08:00:00", 1, 30, 25, 0, 0, 0, 25],
        ]
    )


def volumetria_fato_csv() -> bytes:
    """Fato de volumetria com linhas que DEVEM ser excluidas pelos filtros do
    modelo (instancia DW_STG_PRD, empresa vazia, peso negativo) e uma linha de
    Cross Docking (nao entra em nenhuma das duas metricas — gap conhecido).

    Esperado (RMSPII): 2026-06 recebimento=16000 t, expedicao=16400 t;
    2026-07 recebimento=1000 t.
    """
    return _csv(
        [
            ["NK_INSTANCIA", "NK_CALENDARIO", "NK_EMPRESA", "NK_WMS_FILIAL",
             "NK_CLIENTE", "NK_OPERACAO", "PESO_BRUTO"],
            ["ATIVA_RMSP_PRD", "2026-06-03", "SF", "RMSPII", "05599283", "Recebimento", 16000000],
            ["SLIN_RMSPII_PRD", "2026-06-15", "SF", "RMSPII", "05599283", "Expedição", 16400000],
            ["DW_STG_PRD", "2026-06-10", "SF", "RMSPII", "05599283", "Recebimento", 999999],
            ["ATIVA_RMSP_PRD", "2026-06-11", "", "RMSPII", "05599283", "Recebimento", 5000],
            ["ATIVA_RMSP_PRD", "2026-06-12", "SF", "RMSPII", "05599283", "Recebimento", -10],
            ["ATIVA_RMSP_PRD", "2026-06-13", "SF", "RMSPII", "05599283", "Cross Docking", 7777],
            ["ATIVA_RMSP_PRD", "2026-07-01", "SF", "RMSPII", "05599283", "Recebimento", 1000000],
        ]
    )


ARQUIVOS = {
    "pos_sum": ("pos_sum.xlsx", pos_sum_xlsx),
    "capacidade_hdr": ("capacidade1HDR.csv", capacidade_hdr_csv),
    "ocupacao_comercial": ("ocupacaoComercial.csv", ocupacao_comercial_csv),
    "ocupacao_manual": ("ocupacaoManual.csv", ocupacao_manual_csv),
    "volumetria_fato": ("fato.csv", volumetria_fato_csv),
}
