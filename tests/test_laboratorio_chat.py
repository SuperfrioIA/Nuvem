"""Chat do Laboratorio de Insights (Bloco E / V1.5). Postgres real; o
provedor de IA e sempre mockado via `ia_client.enviar_mensagem` -- nunca
chama a API da Anthropic de verdade (regra do direcionamento: "testes
mockados").
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ia_client, laboratorio, laboratorio_chat
from tests import test_laboratorio as tl

# fixture autouse do modulo do Bloco D -- precisa estar visivel aqui tambem
# (o inventario em cache de processo nao pode vazar de um teste pro outro)
cache_limpo = tl.cache_limpo


def _resposta_ia(texto="resposta simulada", **extra):
    base = {
        "texto": texto,
        "dados": None,
        "modelo": "claude-sonnet-5",
        "effort": "medium",
        "tokens_entrada": 100,
        "tokens_saida": 20,
    }
    base.update(extra)
    return base


def _sessao_com_cliente(monkeypatch, cursor, cliente="SAPORE"):
    tl._arquivo_integrado(
        monkeypatch, linhas=[tl._linha_integrada(cliente=cliente, peso=150.0)]
    )
    return laboratorio.perfilar_selecao(cursor, ["item-016"])


# --- origem (unidade + filial, nunca so o codigo) ---------------------------


def test_origem_do_arquivo_com_de_para_confirmado():
    origem = laboratorio_chat.origem_do_arquivo(
        {"caminho": "RMSPII/ENTRADA/ENTRADA MERCADORIAS/x.xlsx", "filial": "016"}
    )
    assert origem == "RMSPII/016 (RMSPIV)"


def test_origem_do_arquivo_sem_de_para_confirmado():
    origem = laboratorio_chat.origem_do_arquivo(
        {"caminho": "CWB3/ENTRADA/ENTRADA MERCADORIAS/x.xlsx", "filial": "001"}
    )
    assert origem == "CWB3/001 (sem de-para confirmado)"


def test_origem_do_arquivo_sem_filial_no_nome():
    origem = laboratorio_chat.origem_do_arquivo({"caminho": "RMSPII/x.xlsx", "filial": None})
    assert "não identificada" in origem


# --- contexto controlado -----------------------------------------------------


def test_montar_contexto_mascara_cliente_e_leva_unidade_mais_filial(monkeypatch, cursor):
    sessao = _sessao_com_cliente(monkeypatch, cursor, cliente="SAPORE")
    contexto = laboratorio_chat.montar_contexto(sessao)

    assert "SAPORE" not in str(contexto)
    arquivo = contexto["arquivos"][0]
    assert arquivo["origem"] == "RMSPII/016 (RMSPIV)"
    assert arquivo["clientes"]["top"][0]["valor"] == "CLIENTE_1"
    # coluna que soma continua com o total certo -- mascaramento nao toca em numero
    peso = next(c for c in arquivo["colunas"] if c["nome"] == "Peso Bruto")
    assert peso["soma"]["total"] == 150.0


def test_montar_contexto_mascara_o_nome_do_filtro_de_cliente_nas_limitacoes(monkeypatch, cursor):
    """Achado da verificação independente: o texto da limitação de filtro de
    cliente ecoa o nome DIGITADO pelo usuário (não vem só da planilha) --
    tem que sair mascarado igual ao resto."""
    tl._arquivo_integrado(
        monkeypatch,
        linhas=[
            tl._linha_integrada(cliente="SAPORE", peso=100.0),
            tl._linha_integrada(cliente="GR", peso=999.0),
        ],
    )
    sessao = laboratorio.perfilar_selecao(
        cursor, ["item-016"], filtros={"clientes": ["sapore"]}
    )

    contexto = laboratorio_chat.montar_contexto(sessao)

    assert "sapore" not in str(contexto).lower()
    limitacoes = contexto["resumo_da_sessao"]["limitacoes"]
    assert any("cliente_1" in l.lower() for l in limitacoes)


def test_montar_contexto_resumo_filiais_distingue_unidades_com_mesmo_codigo(monkeypatch, cursor):
    """Achado da verificação independente: `perfil["resumo"]["filiais"]` do
    Bloco D é só o código nu -- dois armazéns diferentes com o mesmo código
    (ambiguidade real desde a reestruturação em 4 unidades) colapsavam na
    mesma string dentro do contexto enviado à IA."""
    rmspii = tl._arquivo(
        "ENTRADA_MERCADORIAS_001_2607.xlsx", "item-rmspii",
        caminho="RMSPII/ENTRADA/ENTRADA MERCADORIAS/ENTRADA_MERCADORIAS_001_2607.xlsx",
    )
    cwb3 = tl._arquivo(
        "ENTRADA_MERCADORIAS_001_2607.xlsx", "item-cwb3",
        caminho="CWB3/ENTRADA/ENTRADA MERCADORIAS/ENTRADA_MERCADORIAS_001_2607.xlsx",
    )
    conteudo = tl._xlsx(tl._COLUNAS_INTEGRADA, [tl._linha_integrada()])
    tl._preparar(monkeypatch, [(rmspii, conteudo), (cwb3, conteudo)])

    sessao = laboratorio.perfilar_selecao(cursor, ["item-rmspii", "item-cwb3"])
    contexto = laboratorio_chat.montar_contexto(sessao)

    assert contexto["resumo_da_sessao"]["filiais"] == [
        "CWB3/001 (sem de-para confirmado)",
        "RMSPII/001 (RMSPII)",
    ]


# --- perguntar: caminho feliz -------------------------------------------------


def test_perguntar_grava_pergunta_resposta_e_marca_em_analise(monkeypatch, cursor):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia("ok, entendi os dados"))

    resultado = laboratorio_chat.perguntar(cursor, sessao, "Explique os dados.")

    assert resultado["mensagem_usuario"]["papel"] == "usuario"
    assert resultado["mensagem_usuario"]["conteudo"] == "Explique os dados."
    assert resultado["mensagem_assistente"]["conteudo"] == "ok, entendi os dados"
    assert resultado["mensagem_assistente"]["erro"] is None
    assert resultado["mensagem_assistente"]["modelo"] == "claude-sonnet-5"

    atualizada = laboratorio.obter_sessao(cursor, sessao["id"])
    assert atualizada["status"] == "em_analise"

    mensagens = laboratorio_chat.listar_mensagens(cursor, sessao["id"])
    assert [m["papel"] for m in mensagens] == ["usuario", "assistente"]


def test_perguntar_leva_contexto_mascarado_pra_ia(monkeypatch, cursor):
    sessao = _sessao_com_cliente(monkeypatch, cursor, cliente="SAPORE")
    capturado = {}

    def _capturar(**kw):
        capturado.update(kw)
        return _resposta_ia()

    monkeypatch.setattr(ia_client, "enviar_mensagem", _capturar)
    laboratorio_chat.perguntar(cursor, sessao, "Compare os clientes.")

    conteudo_enviado = str(capturado["mensagens"])
    assert "SAPORE" not in conteudo_enviado
    assert "Compare os clientes." in conteudo_enviado
    assert capturado["modelo"] == "claude-sonnet-5"


def test_perguntar_usa_o_historico_no_segundo_turno(monkeypatch, cursor):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia("primeira resposta"))
    laboratorio_chat.perguntar(cursor, sessao, "Primeira pergunta.")

    capturado = {}

    def _capturar(**kw):
        capturado.update(kw)
        return _resposta_ia("segunda resposta")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _capturar)
    sessao_atualizada = laboratorio.obter_sessao(cursor, sessao["id"])
    laboratorio_chat.perguntar(cursor, sessao_atualizada, "Segunda pergunta.")

    papeis = [m["role"] for m in capturado["mensagens"]]
    assert papeis == ["user", "assistant", "user"]
    assert "Primeira pergunta." in capturado["mensagens"][0]["content"]
    assert capturado["mensagens"][1]["content"] == "primeira resposta"


# --- perguntar: limites e validacoes ------------------------------------------


def test_perguntar_rejeita_pergunta_vazia(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="vazia"):
        laboratorio_chat.perguntar(cursor, sessao, "   ")


def test_perguntar_rejeita_pergunta_acima_do_limite(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="limite"):
        laboratorio_chat.perguntar(cursor, sessao, "x" * (laboratorio_chat.MAX_CARACTERES_PERGUNTA + 1))


def test_perguntar_rejeita_apos_limite_de_mensagens(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia())
    for _ in range(laboratorio_chat.MAX_MENSAGENS_POR_SESSAO // 2):
        laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="limite"):
        laboratorio_chat.perguntar(cursor, sessao, "mais uma")


def test_perguntar_rejeita_sessao_ja_decidida(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    cursor.execute(
        "UPDATE laboratorio_sessoes SET status = 'aprovada' WHERE id = %s", (sessao["id"],)
    )
    sessao_decidida = laboratorio.obter_sessao(cursor, sessao["id"])
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="não aceita novas mensagens"):
        laboratorio_chat.perguntar(cursor, sessao_decidida, "pergunta")


# --- perguntar: falha da IA nunca vira resposta inventada ---------------------


def test_perguntar_sem_chave_configurada_grava_erro_na_mensagem(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")

    assistente = resultado["mensagem_assistente"]
    assert assistente["conteudo"] == ""
    assert "ANTHROPIC_API_KEY" in assistente["erro"]
    # a conversa segue -- sessao vira em_analise, nao fica travada
    assert laboratorio.obter_sessao(cursor, sessao["id"])["status"] == "em_analise"


def test_perguntar_com_recusa_da_ia_grava_erro_sem_lancar(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)

    def _recusar(**kw):
        raise ia_client.IARecusadaError("recusado por política")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _recusar)
    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    assert "recusado" in resultado["mensagem_assistente"]["erro"]


def test_perguntar_com_provedor_indisponivel_grava_erro_sem_lancar(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)

    def _indisponivel(**kw):
        raise ia_client.IAIndisponivelError("timeout ao chamar o provedor de IA")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _indisponivel)
    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    assert "timeout" in resultado["mensagem_assistente"]["erro"]


def test_erro_de_uma_mensagem_nao_entra_no_historico_reenviado_a_ia(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)

    def _indisponivel(**kw):
        raise ia_client.IAIndisponivelError("fora do ar")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _indisponivel)
    laboratorio_chat.perguntar(cursor, sessao, "primeira")

    capturado = {}

    def _capturar(**kw):
        capturado.update(kw)
        return _resposta_ia("respondeu")

    monkeypatch.setattr(ia_client, "enviar_mensagem", _capturar)
    sessao_atualizada = laboratorio.obter_sessao(cursor, sessao["id"])
    laboratorio_chat.perguntar(cursor, sessao_atualizada, "segunda")

    # a mensagem de assistente com erro nunca vira contexto pra IA -- so os
    # dois turnos de usuario ficam (a API funde "user" consecutivos)
    assert [m["role"] for m in capturado["mensagens"]] == ["user", "user"]
    assert "fora do ar" not in str(capturado["mensagens"])


# --- feedback -----------------------------------------------------------------


def test_registrar_feedback_grava_tipo_e_comentario(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia())
    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    mensagem_id = resultado["mensagem_assistente"]["id"]

    laboratorio_chat.registrar_feedback(cursor, sessao["id"], mensagem_id, "pedir_ajuste", "faltou X")

    mensagens = laboratorio_chat.listar_mensagens(cursor, sessao["id"])
    assistente = next(m for m in mensagens if m["papel"] == "assistente")
    assert assistente["feedback"] == "pedir_ajuste"
    assert assistente["feedback_comentario"] == "faltou X"


def test_registrar_feedback_tipo_invalido_falha(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia())
    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="inválido"):
        laboratorio_chat.registrar_feedback(
            cursor, sessao["id"], resultado["mensagem_assistente"]["id"], "amei", None
        )


def test_registrar_feedback_em_mensagem_de_usuario_falha(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia())
    resultado = laboratorio_chat.perguntar(cursor, sessao, "pergunta")
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="mensagem do assistente"):
        laboratorio_chat.registrar_feedback(
            cursor, sessao["id"], resultado["mensagem_usuario"]["id"], "gostei", None
        )


def test_registrar_feedback_mensagem_inexistente_falha(cursor, monkeypatch):
    sessao = _sessao_com_cliente(monkeypatch, cursor)
    with pytest.raises(laboratorio_chat.LaboratorioChatError, match="não encontrada"):
        laboratorio_chat.registrar_feedback(cursor, sessao["id"], 999999, "gostei", None)


# --- endpoints -----------------------------------------------------------------


def test_endpoints_de_chat_sem_login_dao_401(banco_migrado):
    with TestClient(app) as c:
        assert c.get("/api/admin/laboratorio/sessoes/1/mensagens").status_code == 401
        assert c.post("/api/admin/laboratorio/sessoes/1/mensagens", json={"pergunta": "x"}).status_code == 401
        assert c.post(
            "/api/admin/laboratorio/sessoes/1/mensagens/1/feedback", json={"tipo": "gostei"}
        ).status_code == 401
        assert c.post("/api/admin/laboratorio/sessoes/1/aprovar", json={}).status_code == 401
        assert c.post("/api/admin/laboratorio/sessoes/1/descartar", json={}).status_code == 401


def test_endpoint_mensagens_sessao_inexistente_da_404(cliente):
    resposta = cliente.post(
        "/api/admin/laboratorio/sessoes/99999/mensagens", json={"pergunta": "x"}
    )
    assert resposta.status_code == 404


def test_endpoint_pergunta_e_feedback_via_http(cliente, monkeypatch):
    tl._arquivo_integrado(monkeypatch)
    sessao = cliente.post(
        "/api/admin/laboratorio/perfil", json={"item_ids": ["item-016"]}
    ).json()

    monkeypatch.setattr(ia_client, "enviar_mensagem", lambda **kw: _resposta_ia("resposta via http"))
    resposta = cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/mensagens",
        json={"pergunta": "Explique os dados.", "mensagem_sugerida": None},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["mensagem_assistente"]["conteudo"] == "resposta via http"

    listagem = cliente.get(f"/api/admin/laboratorio/sessoes/{sessao['id']}/mensagens").json()
    assert len(listagem["mensagens"]) == 2

    feedback = cliente.post(
        f"/api/admin/laboratorio/sessoes/{sessao['id']}/mensagens/"
        f"{corpo['mensagem_assistente']['id']}/feedback",
        json={"tipo": "gostei"},
    )
    assert feedback.status_code == 200
