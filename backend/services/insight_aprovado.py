"""Promoção de insight para KPI (Bloco E / V1.6).

Ao aprovar uma sessão de análise, gera a ESPECIFICAÇÃO TÉCNICA da seção 10 do
direcionamento -- nunca publica KPI, nunca calcula nada. É o documento que um
humano usa depois pra implementar o indicador de verdade:

    Insight aprovado -> Especificação técnica -> Implementação -> Testes
    -> Validação -> Publicação

Os campos que o código já apurou de forma determinística (fontes, campos,
conceitos, unidade, granularidade, limitações -- tudo já vive no perfil da
sessão, calculado no Bloco D) vêm direto de lá, nunca da IA: a IA não pode
inventar unidade/fonte que o perfil não declarou. A parte que só a conversa
sabe (nome, pergunta de negócio, fórmula em português, riscos, exemplos
concretos) é pedida à IA em SAÍDA ESTRUTURADA (schema fixo) -- sempre um
rascunho pra revisão humana, nunca publicação automática.
"""

import json

from backend.config import ConfiguracaoIAIncompletaError, obter_configuracao_ia

from . import ia_client, laboratorio, laboratorio_chat

_STATUS_TERMINAIS = ("aprovada", "descartada")

_ESQUEMA_ESPECIFICACAO = {
    "type": "object",
    "properties": {
        "nome": {"type": "string"},
        "pergunta_negocio": {"type": "string"},
        "formula": {"type": "string"},
        "riscos": {"type": "array", "items": {"type": "string"}},
        "exemplos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["nome", "pergunta_negocio", "formula", "riscos", "exemplos"],
    "additionalProperties": False,
}

_SISTEMA_ESPECIFICACAO = (
    "Com base na conversa e no perfil dos dados abaixo, redija um RASCUNHO de "
    "especificação de indicador para revisão humana -- você não está "
    "publicando nem calculando o indicador oficial, só estruturando o que foi "
    "discutido. Nome curto, pergunta de negócio em uma frase, fórmula descrita "
    "em português (nunca invente unidade, fonte ou conceito que não apareceu "
    "no perfil ou na conversa), riscos e exemplos concretos tirados da "
    "conversa."
)


class InsightAprovadoError(Exception):
    """Erro de fluxo da aprovação/descarte -- o endpoint traduz pra HTTP 400."""


def _fontes_campos_conceitos(perfil: dict) -> dict:
    """Parte determinística da especificação -- direto do perfil já calculado
    no Bloco D, nunca da IA."""
    fontes, campos, conceitos, unidades = [], [], set(), set()
    granularidades, limitacoes = set(), set()
    for arquivo in perfil["arquivos"]:
        fontes.append(
            {
                "arquivo": arquivo["arquivo"],
                "familia": arquivo["familia"],
                "caminho": arquivo["caminho"],
                "origem": laboratorio_chat.origem_do_arquivo(arquivo),
            }
        )
        granularidades.add(arquivo["granularidade_provavel"])
        limitacoes.update(arquivo["limitacoes"])
        for coluna in arquivo["colunas"]:
            if coluna["soma_permitida"]:
                campos.append(
                    {
                        "arquivo": arquivo["arquivo"],
                        "coluna": coluna["nome"],
                        "conceito": coluna["conceito"],
                        "unidade": coluna["unidade"],
                    }
                )
                if coluna["conceito"]:
                    conceitos.add(coluna["conceito"])
                if coluna["unidade"]:
                    unidades.add(coluna["unidade"])
    return {
        "fontes": fontes,
        "campos": campos,
        "conceitos": sorted(conceitos),
        "unidades": sorted(unidades),
        "granularidade": sorted(granularidades),
        "limitacoes": sorted(limitacoes),
    }


def gerar_especificacao(cur, sessao: dict) -> dict:
    historico = laboratorio_chat.listar_mensagens(cur, sessao["id"])
    if not historico:
        raise InsightAprovadoError(
            "sessão sem nenhuma mensagem de chat -- converse antes de aprovar"
        )

    contexto = laboratorio_chat.montar_contexto(sessao)
    conversa = "\n".join(
        f"{'Usuário' if m['papel'] == 'usuario' else 'Assistente'}: {m['conteudo']}"
        for m in historico
        if not (m["papel"] == "assistente" and m["erro"])
    )
    mensagens = [
        {
            "role": "user",
            "content": (
                laboratorio_chat.formatar_contexto(contexto)
                + "\n\n<conversa>\n"
                + conversa
                + "\n</conversa>"
            ),
        }
    ]

    # ao contrário do chat (que grava o erro numa mensagem e segue), aprovar é
    # uma ação única -- achado da verificação independente: sem este
    # try/except, falha da IA aqui subia crua até o endpoint e virava HTTP
    # 500 em vez do 400 tratado que o resto do Laboratório sempre devolve.
    try:
        config = obter_configuracao_ia()
        resultado = ia_client.enviar_mensagem(
            system=_SISTEMA_ESPECIFICACAO,
            mensagens=mensagens,
            modelo=config.modelo,
            effort=config.effort,
            schema=_ESQUEMA_ESPECIFICACAO,
        )
    except (ConfiguracaoIAIncompletaError, ia_client.IAError) as exc:
        raise InsightAprovadoError(f"não foi possível gerar a especificação: {exc}") from exc
    rascunho = resultado["dados"]

    return {
        "nome": rascunho["nome"],
        "pergunta_negocio": rascunho["pergunta_negocio"],
        "formula": rascunho["formula"],
        "riscos": rascunho["riscos"],
        "exemplos": rascunho["exemplos"],
        **_fontes_campos_conceitos(sessao["perfil"]),
        "dimensoes": ["período", "filial", "cliente"],
        "filtros": sessao["filtros"],
        "evidencias": {"mensagens": [m["id"] for m in historico]},
        "historico_conversa": [
            {"papel": m["papel"], "conteudo": m["conteudo"], "criado_em": m["criado_em"]}
            for m in historico
        ],
        "gerado_por_modelo": resultado["modelo"],
    }


def _exigir_sessao_nao_decidida(sessao: dict | None) -> None:
    if sessao is None:
        raise InsightAprovadoError("sessão de análise não encontrada")
    if sessao["status"] in _STATUS_TERMINAIS:
        raise InsightAprovadoError(
            f"sessão já está '{sessao['status']}' -- decisão é definitiva"
        )


def aprovar(cur, sessao_id: int, nota: str | None = None) -> dict:
    sessao = laboratorio.obter_sessao(cur, sessao_id)
    _exigir_sessao_nao_decidida(sessao)

    especificacao = gerar_especificacao(cur, sessao)
    cur.execute(
        """
        UPDATE laboratorio_sessoes
        SET status = 'aprovada', especificacao = %s, decisao_nota = %s, decidido_em = now()
        WHERE id = %s
        """,
        (json.dumps(especificacao, ensure_ascii=False), nota, sessao_id),
    )
    return especificacao


def descartar(cur, sessao_id: int, motivo: str | None = None) -> None:
    sessao = laboratorio.obter_sessao(cur, sessao_id)
    _exigir_sessao_nao_decidida(sessao)
    cur.execute(
        """
        UPDATE laboratorio_sessoes
        SET status = 'descartada', decisao_nota = %s, decidido_em = now()
        WHERE id = %s
        """,
        (motivo, sessao_id),
    )
