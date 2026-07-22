"""Ponta a ponta pela API (TestClient + Postgres real): os 5 fluxos de upload
do Lote 8 com os mapeamentos reais, idempotencia do reprocesso, pendencia de
de-para e limite de tamanho.

Os arquivos sao sinteticos (tests/arquivos_sinteticos.py) — provam a
estabilidade tecnica do fluxo, nao substituem a validacao visual dos
relatorios reais.
"""

import json

import pytest

from tests import arquivos_sinteticos, modelos_reais
from tests.conftest import consultar

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload(cliente, chave: str, modelo_id: int | None = None):
    nome_arquivo, gerador = arquivos_sinteticos.ARQUIVOS[chave]
    mime = XLSX_MIME if nome_arquivo.endswith(".xlsx") else "text/csv"
    data = {}
    if modelo_id:
        data["modelo_id"] = str(modelo_id)
    else:
        data["nome_novo_modelo"] = chave
        data["mapeamento_json"] = json.dumps(modelos_reais.TODOS[chave])
    return cliente.post(
        "/api/admin/upload/processar",
        files={"arquivo": (nome_arquivo, gerador(), mime)},
        data=data,
    )


def _medidas() -> set[tuple]:
    return set(
        consultar(
            """
            SELECT a.sigla, m.nome, md.competencia::text, md.valor::float
            FROM medidas md
            JOIN armazens a ON a.id = md.armazem_id
            JOIN metricas m ON m.id = md.metrica_id
            """
        )
    )


def test_os_cinco_fluxos_reais(cliente):
    for chave in arquivos_sinteticos.ARQUIVOS:
        resposta = _upload(cliente, chave)
        assert resposta.status_code == 200, f"{chave}: {resposta.text}"
        corpo = resposta.json()
        assert corpo["modelo_id"], chave
        assert corpo["linhas_lidas"] > 0, chave

    medidas = _medidas()
    # amostras conferidas a mao, uma por fonte (valores dos arquivos sinteticos)
    assert ("RMSPIII", "posicoes_ocupadas", "2026-07-01", 9773.0) in medidas       # pos_sum
    assert ("RMSPIII", "posicoes_virtuais", "2026-07-01", 578.0) in medidas        # pos_sum
    assert ("RMSPIII", "capacidade_total", "2026-07-01", 12170.0) in medidas       # hdr sobrescreve pos_sum (mesmo valor)
    assert ("RMSPIII", "comercial_vigente", "2026-07-01", 9773.0) in medidas       # comercial via FK 46
    assert ("RMSP", "ocupacao_manual", "2026-07-01", 700.0) in medidas             # manual via FK 30
    assert ("RMSPII", "volumetria_recebimento", "2026-06-01", 16000.0) in medidas  # fato
    assert ("RMSPII", "volumetria_expedicao", "2026-06-01", 16400.0) in medidas    # fato

    # sem nenhuma pendencia: todos os apelidos sinteticos existem no seed
    assert consultar("SELECT count(*) FROM depara_pendencias")[0][0] == 0

    # scores recalculados ao fim de cada processamento
    assert consultar("SELECT count(*) FROM scores")[0][0] > 0

    # execucoes registradas com arquivo retido
    execucoes = consultar("SELECT status, arquivo_path FROM execucoes")
    assert len(execucoes) == 5
    assert all(status == "ok" and arquivo for status, arquivo in execucoes)


def test_reprocesso_com_modelo_salvo_e_idempotente(cliente):
    primeira = _upload(cliente, "volumetria_fato")
    assert primeira.status_code == 200
    modelo_id = primeira.json()["modelo_id"]
    antes = _medidas()
    modelos_antes = consultar("SELECT count(*) FROM modelos_importacao")[0][0]

    segunda = _upload(cliente, "volumetria_fato", modelo_id=modelo_id)
    assert segunda.status_code == 200
    assert segunda.json()["modelo_id"] == modelo_id

    assert _medidas() == antes  # mesmos valores, nada duplicado
    # modelo reutilizado, nao recriado (delta zero — robusto aos modelos canonicos
    # semeados no startup a partir do Lote R1.1)
    assert consultar("SELECT count(*) FROM modelos_importacao")[0][0] == modelos_antes


def test_armazem_sem_depara_vira_pendencia(cliente):
    conteudo = arquivos_sinteticos._csv(
        [
            ["NK_INSTANCIA", "NK_CALENDARIO", "NK_EMPRESA", "NK_WMS_FILIAL",
             "NK_CLIENTE", "NK_OPERACAO", "PESO_BRUTO"],
            ["ATIVA_RMSP_PRD", "2026-06-03", "SF", "FILIAL_NOVA_XYZ", "1", "Recebimento", 1000],
        ]
    )
    resposta = cliente.post(
        "/api/admin/upload/processar",
        files={"arquivo": ("fato.csv", conteudo, "text/csv")},
        data={"nome_novo_modelo": "volumetria_fato",
              "mapeamento_json": json.dumps(modelos_reais.VOLUMETRIA_FATO)},
    )
    assert resposta.status_code == 200
    assert consultar(
        "SELECT armazem_na_fonte FROM depara_pendencias"
    ) == [("FILIAL_NOVA_XYZ",)]
    assert consultar("SELECT count(*) FROM medidas")[0][0] == 0


def test_limite_de_upload(cliente, monkeypatch):
    monkeypatch.setenv("UPLOAD_MAX_MB", "0")  # limite zero: qualquer arquivo estoura
    resposta = _upload(cliente, "volumetria_fato")
    assert resposta.status_code == 413
    assert "limite" in resposta.json()["detail"]


def test_preview(cliente):
    nome, gerador = arquivos_sinteticos.ARQUIVOS["pos_sum"]
    resposta = cliente.post(
        "/api/admin/upload/preview", files={"arquivo": (nome, gerador(), XLSX_MIME)}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "Filial" in corpo["colunas"] and "Ocup Pos" in corpo["colunas"]
    assert len(corpo["amostra"]) >= 1


def test_sem_login_e_401(banco_migrado):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as anonimo:
        resposta = anonimo.get("/api/admin/execucoes")
        assert resposta.status_code == 401
