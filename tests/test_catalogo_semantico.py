"""Testes do catalogo semantico (Bloco B / V1.1): migration 0005, seeds
idempotentes e endpoints do painel. Postgres real via fixtures do conftest."""

from fastapi.testclient import TestClient

from backend.database import init_db
from backend.main import app
from tests.conftest import consultar


# --- seed: unidades ----------------------------------------------------------


def test_unidades_semeadas_com_categoria_e_fator(banco_migrado):
    linhas = consultar(
        "SELECT categoria, fator_para_base, base_da_categoria FROM unidades WHERE chave = 't'"
    )
    assert linhas == [("massa", 1000, False)]
    (base_massa,) = consultar(
        "SELECT chave FROM unidades WHERE categoria = 'massa' AND base_da_categoria"
    )[0]
    assert base_massa == "kg"


def test_estrutura_logistica_nao_tem_conversao(banco_migrado):
    linhas = consultar(
        """
        SELECT chave, fator_para_base FROM unidades
        WHERE categoria = 'estrutura_logistica'
        """
    )
    assert len(linhas) >= 3
    assert all(fator is None for _, fator in linhas)


# --- seed: conceitos e campos ------------------------------------------------


def test_conceitos_canonicos_semeados(banco_migrado):
    linhas = consultar(
        """
        SELECT unidade_canonica, categoria_unidade, agregacao_padrao, status
        FROM conceitos_canonicos WHERE chave = 'peso_bruto_movimentado'
        """
    )
    assert linhas == [("kg", "massa", "soma", "aprovado")]

    # volumes nao tem unidade canonica unica de proposito (embalagens mistas)
    linhas = consultar(
        """
        SELECT unidade_canonica, categoria_unidade FROM conceitos_canonicos
        WHERE chave = 'volumes_declarados'
        """
    )
    assert linhas == [(None, "embalagem")]


def test_familias_datahub_viram_fontes_logicas(banco_migrado):
    (total,) = consultar(
        "SELECT COUNT(*) FROM catalogo_fontes WHERE tipo_origem = 'sharepoint_datahub'"
    )[0]
    assert total == 9  # 8 familias + PALLETS_EXCEDENTES (PDF)


def test_campos_entrada_mercadorias_completos(banco_migrado):
    linhas = consultar(
        """
        SELECT c.posicao, c.nome_original, cc.chave, c.unidade_original,
               c.unidade_por_coluna, c.categoria_unidade
        FROM catalogo_campos c
        LEFT JOIN conceitos_canonicos cc ON cc.id = c.conceito_id
        JOIN catalogo_fontes f ON f.id = c.fonte_id
        WHERE f.chave = 'datahub_entrada_mercadorias'
        ORDER BY c.posicao
        """
    )
    assert len(linhas) == 20

    por_posicao = {linha[0]: linha for linha in linhas}
    # EMB duplicado convive porque a identidade e a POSICAO (10 e 12)
    assert por_posicao[10][1] == "EMB"
    assert por_posicao[12][1] == "EMB"
    # Volume: conceito volumes_declarados, unidade linha a linha via EMB (pos 10)
    assert por_posicao[9][1] == "Volume"
    assert por_posicao[9][2] == "volumes_declarados"
    assert por_posicao[9][3] is None
    assert por_posicao[9][4] == 10
    assert por_posicao[9][5] == "embalagem"
    # Peso Bruto: kg, massa, conceito canonico
    assert por_posicao[14][2] == "peso_bruto_movimentado"
    assert por_posicao[14][3] == "kg"


def test_seed_semantico_e_idempotente(banco_migrado):
    contagens = lambda: consultar(  # noqa: E731
        """
        SELECT (SELECT COUNT(*) FROM unidades),
               (SELECT COUNT(*) FROM conceitos_canonicos),
               (SELECT COUNT(*) FROM catalogo_campos),
               (SELECT COUNT(*) FROM catalogo_fontes)
        """
    )[0]
    antes = contagens()
    init_db()  # segunda rodada de seeds
    assert contagens() == antes


# --- endpoints do painel -----------------------------------------------------


def test_endpoints_semantica_exigem_login(banco_migrado):
    with TestClient(app) as c:
        for caminho in ("/unidades", "/conceitos", "/fontes", "/campos?fonte_id=1"):
            assert c.get("/api/admin/semantica" + caminho).status_code == 401


def test_endpoint_conceitos_e_unidades(cliente):
    conceitos = cliente.get("/api/admin/semantica/conceitos").json()
    assert {c["chave"] for c in conceitos} >= {
        "peso_bruto_movimentado", "valor_mercadoria_movimentada", "volumes_declarados",
    }

    unidades = cliente.get("/api/admin/semantica/unidades").json()
    t = next(u for u in unidades if u["chave"] == "t")
    assert t["categoria"] == "massa"
    assert t["fator_para_base"] == 1000.0


def test_endpoint_campos_por_fonte(cliente):
    fontes = cliente.get("/api/admin/semantica/fontes").json()
    assert len(fontes) == 1  # so a familia integrada tem campos por ora
    assert fontes[0]["chave"] == "datahub_entrada_mercadorias"
    assert fontes[0]["total_campos"] == 20

    campos = cliente.get(f"/api/admin/semantica/campos?fonte_id={fontes[0]['id']}").json()
    volume = next(c for c in campos if c["nome_original"] == "Volume")
    # unidade canonica derivada do conceito (nenhuma, no caso do volume)
    assert volume["conceito_chave"] == "volumes_declarados"
    assert volume["unidade_canonica"] is None
    peso = next(c for c in campos if c["nome_original"] == "Peso Bruto")
    assert peso["unidade_canonica"] == "kg"


def test_endpoint_campos_fonte_sem_campos_da_404(cliente):
    (fonte_id,) = consultar(
        "SELECT id FROM catalogo_fontes WHERE chave = 'datahub_guias_entrada'"
    )[0]
    resposta = cliente.get(f"/api/admin/semantica/campos?fonte_id={fonte_id}")
    assert resposta.status_code == 404
